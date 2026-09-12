"""Browser + production Store/TTS test adapter, NOT Flask nor real Tailscale.

Real Swedish WAV synthesis through installed eSpeak/eSpeak NG, real WebAudio
in Chromium, Jinja templates from this tree. No physical speaker assertion.
"""
import json
import os
import re
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from familj.store import Store
from familj.voice54 import VoiceStore,Synthesizer,VoiceError
from familj.remote_access import status_from
from render_support import environment,context,seed,NOW,weather_fixture
OUT=Path(os.environ.get('FAMILJ_TEST_OUTPUT',str(ROOT.parent/'homevoice54-results')));OUT.mkdir(parents=True,exist_ok=True)
reports=[]

def check(name,condition):
    assert condition,name
    reports.append(dict(test=name,passed=True));print('OK '+name,flush=True)

with tempfile.TemporaryDirectory() as tmp:
    store=Store(Path(tmp),now=lambda:NOW);seed(store);v=VoiceStore(store);synth=Synthesizer(store.data);env=environment(store)
    v.save(4,dict(enabled='on',rewards='on',notes='on',speed=155,volume=65))
    host='familj.example.ts.net'
    ts={'BackendState':'Running','Self':{'DNSName':host+'.'}}
    conf={'TCP':{'443':{'HTTPS':True}},'Web':{host+':443':{'Handlers':{'/':{'Proxy':'http://127.0.0.1:5000'}}}}}
    remote=status_from(ts,conf,{},True)
    posts=[]
    # No network navigation: this environment blocks browser HTTP. Render local
    # files and supply a fetch adapter, as in the previous project's tests.
    import base64
    def adapter(path, options):
        p=urlparse(path).path;q=parse_qs(urlparse(path).query)
        payload=json.loads(options.get('body','{}'))
        if options.get('method')=='POST':posts.append((p,payload))
        m=re.fullmatch(r'/api/voice/profile/(\d+)(/audio)?',p)
        if m:
            uid=int(m[1]);info=synth.status()
            if m[2]:
                try:
                    text,cfg=v.text(uid,payload['kind'],payload.get('task_id'))
                    data=synth.synthesize(uid,text,cfg['speed'])
                    return dict(status=200,audio=base64.b64encode(data).decode())
                except (VoiceError,ValueError,LookupError) as e:return dict(status=getattr(e,'status',400),data={'error':str(e)})
            return dict(status=200,data=dict(ok=True,settings=v.settings(uid),pending_ids=v.pending(uid),engine=dict(ready=info['ready'],name=info['engine'],message=info['message']),version=store.version()))
        if p=='/admin/mobile/status':return dict(status=200,data=remote)
        if p=='/api/weather':return dict(status=200,data=weather_fixture())
        if p=='/api/state':
            view=q.get('view',['home'])[0];uid=int(q.get('user_id',['1'])[0]);data=dict(version=store.version(),release='preview',now=store.now().isoformat(),settings=store.settings())
            if q.get('since',[''])[0]!=str(store.version()) and view in ('home','user','badges'):
                data['html']=env.get_template('partials/'+view+'_content.html').render(**context(store,view,uid))
            return dict(status=200,data=data)
        m=re.fullmatch(r'/api/tasks/(\d+)/complete',p)
        if m:return dict(status=200,data=store.set_completed(int(m[1]),payload['completed']))
        return dict(status=404,data={})
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--disable-gpu'])
        ctx=browser.new_context(viewport={'width':1280,'height':720},has_touch=True)
        page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.expose_function('_voiceAdapter',adapter)
        def load(path):
            page.goto('about:blank')
            if path.startswith('/user/'):
                template='user.html';data=context(store,'user',int(path.split('/')[-1]))
            elif path=='/admin/speech':
                template='speech54.html';data=context(store,'admin')|dict(voice_users=[v.settings(u['id']) for u in store.users()],voice_engine=synth.status(),voice_error=None)
            else:template='mobile54.html';data=context(store,'admin')|dict(remote=remote)
            html=env.get_template(template).render(**data)
            styles=re.findall(r'<link rel="stylesheet" href="([^"]+)"[^>]*>',html)
            scripts=re.findall(r'<script src="([^"]+)"[^>]*></script>',html)
            html=re.sub(r'<script src="[^"]+"[^>]*></script>','',html)
            html=re.sub(r'<link rel="stylesheet"[^>]*>','',html)
            page.set_content(html)
            for style in styles:page.add_style_tag(content=(ROOT/'static'/Path(urlparse(style).path).name).read_text())
            page.evaluate("""() => {
                window.fetch=async (path,options={})=>{
                    const r=await window._voiceAdapter(String(path),options);
                    if(r.audio){const bytes=Uint8Array.from(atob(r.audio),c=>c.charCodeAt(0));return new Response(bytes,{status:r.status,headers:{'Content-Type':'audio/wav'}});}
                    return new Response(JSON.stringify(r.data),{status:r.status,headers:{'Content-Type':'application/json'}});
                };
            }""")
            for script in scripts:page.add_script_tag(content=(ROOT/'static'/Path(urlparse(script).path).name).read_text())
        load('/user/4');page.wait_for_selector('[data-voice-action="all"]')
        check('Enabled profile has read-all and per-task controls',page.locator('[data-voice-action="task"]').count()>0)
        check('Touch engine remains active',page.evaluate('!!window.HemmaTouchScroll'))
        check('Scrollbar stays hidden',page.evaluate('getComputedStyle(document.documentElement).scrollbarWidth')=='none')
        page.screenshot(path=str(OUT/'profile.png'))
        before=len(posts)
        page.locator('[data-voice-action="task"]').first.click()
        page.wait_for_function('document.querySelector("[data-voice-status]").textContent.includes("klar.")',timeout=16000)
        check('Real Swedish WAV decoded and played in WebAudio',any(p[0].endswith('/audio') for p in posts[before:]))
        check('Read button did not mark task complete',not any('/complete' in p[0] for p in posts[before:]))
        page.locator('[data-voice-action="all"]').click();page.wait_for_timeout(200);page.locator('[data-voice-action="stop"]').click()
        check('Stop cancels reading',page.evaluate('window.HemmaVoice54.busy') is False)
        check('Stop has visible feedback','Stoppad' in page.locator('[data-voice-status]').inner_text())
        # Complete a real task; observe overlay, then confirm reward request carries tid.
        page.locator('.pending-tasks .task-check').first.click()
        page.wait_for_function('document.getElementById("reward").hidden===false')
        page.wait_for_timeout(500)
        check('Reward speech used actual completed task id',any(p[1].get('kind')=='reward' and isinstance(p[1].get('task_id'),int) for p in posts))
        page.wait_for_timeout(3600)
        check('Live state update restores voice controls',page.locator('[data-voice-action="all"]').count()==1)
        # Disabled config arrives without rewriting touch handlers.
        v.save(4,dict(enabled='',speed=155,volume=65))
        page.evaluate('document.dispatchEvent(new Event("visibilitychange"))')
        page.wait_for_function('document.querySelector("[data-voice-action=all]")===null')
        check('Turning voice off removes controls without reload',page.locator('[data-voice-action="task"]').count()==0)
        load('/user/2');page.wait_for_timeout(300)
        check('Other profile has no read controls',page.locator('[data-voice-toolbar]').count()==0)
        for width in [390,1280]:
            page.set_viewport_size({'width':width,'height':844 if width==390 else 720})
            load('/admin/speech');page.wait_for_timeout(150)
            check(f'Voice admin {width} no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            check(f'Voice admin {width} no kiosk engine',not page.evaluate('!!window.HemmaTouchScroll'))
            check(f'Voice admin {width} editable volume works',page.locator('input[name="volume"]').first.is_editable())
            if width==390:page.screenshot(path=str(OUT/'speech-mobile.png'),full_page=True)
            load('/admin/mobile');page.wait_for_timeout(150)
            check(f'Mobile guide {width} shows canonical verified URL',page.locator('#mobile54-url').input_value()=='https://familj.example.ts.net/admin')
            check(f'Mobile guide {width} no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            page.locator('#mobile54-refresh').click();page.wait_for_timeout(150)
            check(f'Mobile guide {width} address unchanged on refresh',page.locator('#mobile54-url').input_value()=='https://familj.example.ts.net/admin')
            check(f'Mobile guide {width} manifest has relative origin',page.locator('link[rel="manifest"]').get_attribute('href')=='/mobile.webmanifest')
            if width==390:page.screenshot(path=str(OUT/'mobile-address.png'),full_page=True)
        check('No browser JavaScript exceptions',not errors)
        (OUT/'results.json').write_text(json.dumps(dict(tests=reports,passed=len(reports),failed=0,browser=browser.version,method='Jinja + production Store/TTS fetch adapter; NOT Flask; no physical speaker or real Tailscale'),indent=2))
        ctx.close();browser.close()
print(str(len(reports))+' browser checks passed',flush=True)

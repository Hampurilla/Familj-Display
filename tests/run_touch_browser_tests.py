"""Real Chromium pointer tests on locally rendered application HTML.

No external requests. A small in-memory fetch adapter supplies production Store
results; this is not an end-to-end Flask test and not a physical Pi test.
Run from repo root: python tests/run_touch_browser_tests.py
Requires playwright, jinja2 and a Chromium executable (CHROMIUM env var).
"""
from __future__ import annotations
import json
import os
import re
import sys
import tempfile
import time
import traceback
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from familj.store import Store
from render_support import seed,environment,context,NOW,weather_fixture

RESULTS=ROOT.parent/'results'
RESULTS.mkdir(exist_ok=True)


def main():
    from playwright.sync_api import sync_playwright
    reports=[]
    with tempfile.TemporaryDirectory(prefix='touch-checks-') as temp:
        store=Store(Path(temp),now=lambda:NOW);seed(store)
        for index in range(5,17):store.save_user('Profil '+str(index))
        for index in range(24):
            store.save_template(dict(title='Testuppgift '+str(index),difficulty=2,start_date='2026-09-09',recurrence='once',assignment_mode='fixed',fixed_user_id=1,eligible_ids=[]))
        env=environment(store)

        def fetch(path,options):
            u=urlparse(path);q=parse_qs(u.query)
            if u.path=='/api/weather':return dict(status=200,data=weather_fixture())
            if u.path=='/api/state':
                view=q.get('view',['home'])[0];uid=int(q['user_id'][0]) if 'user_id' in q else None
                data=dict(version=store.version(),release='preview',now=store.now().isoformat(),settings=store.settings())
                if q.get('since',['-1'])[0]!=str(store.version()) and view in ('home','user','badges'):
                    env.globals.update(settings=store.settings())
                    data['html']=env.get_template('partials/'+view+'_content.html').render(**context(store,view,uid))
                return dict(status=200,data=data)
            m=re.fullmatch(r'/api/tasks/(\d+)/complete',u.path)
            if m:return dict(status=200,data=store.set_completed(int(m[1]),json.loads(options.get('body','{}'))['completed']))
            return dict(status=404,data={'error':'test route not defined'})

        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM','/usr/bin/chromium'),args=['--disable-gpu'])
            print('Chromium '+browser.version,flush=True)

            def make(view='home',touch=False,motion='reduce',width=1280,height=720,tab='settings'):
                ctx=browser.new_context(viewport={'width':width,'height':height},has_touch=touch,reduced_motion=motion)
                page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.expose_function('_fixtureFetch',fetch)
                if view=='test':html=(ROOT/'static/touch-test.html').read_text()
                else:html=env.get_template(view+'.html').render(**context(store,view,1,tab=tab))
                # Embedded resources are added from disk: no HTTP or policy changes.
                scripts=re.findall(r'<script src="([^"]+)"[^>]*></script>',html)
                styles=re.findall(r'<link rel="stylesheet" href="([^"]+)"[^>]*>',html)
                html=re.sub(r'<script src="[^"]+"[^>]*></script>','',html)
                html=re.sub(r'<link rel="(?:stylesheet|icon)"[^>]*>','',html)
                page.set_content(html)
                for s in styles:
                    name=Path(urlparse(s).path).name
                    page.add_style_tag(content=(ROOT/'static'/name).read_text())
                page.evaluate('''() => {
                    window.__nav=[];window.__posts=[];
                    window.fetch=async (path, options={})=>{
                        if(options.method==='POST')window.__posts.push({path,body:options.body});
                        const result=await window._fixtureFetch(String(path),options);
                        return new Response(JSON.stringify(result.data),{status:result.status,headers:{'Content-Type':'application/json'}});
                    };
                }''')
                for s in scripts:
                    page.add_script_tag(content=(ROOT/'static'/Path(urlparse(s).path).name).read_text())
                # Capture only uncancelled anchor activations; don't navigate away
                # from the offline fixture. Dragged links must never reach here.
                page.evaluate('''() => document.addEventListener('click',event=>{
                    const a=event.target.closest('a[href]');
                    if(a&&!event.defaultPrevented){window.__nav.push(a.getAttribute('href'));event.preventDefault();}
                })''')
                page.wait_for_timeout(80)
                return ctx,page,errors

            def drag(page,start=(16,620),end=(16,240),touch=False,steps=14,wait=14,release=True):
                if touch:
                    c=page.context.new_cdp_session(page)
                    c.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':start[0],'y':start[1],'id':1}]})
                    for i in range(1,steps+1):
                        x=start[0]+(end[0]-start[0])*i/steps;y=start[1]+(end[1]-start[1])*i/steps
                        c.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x,'y':y,'id':1}]});page.wait_for_timeout(wait)
                    if release:c.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
                    c.detach()
                else:
                    page.mouse.move(*start);page.mouse.down()
                    for i in range(1,steps+1):
                        page.mouse.move(start[0]+(end[0]-start[0])*i/steps,start[1]+(end[1]-start[1])*i/steps)
                        page.wait_for_timeout(wait)
                    if release:page.mouse.up()

            def pos(page,selector):
                loc=page.locator(selector).first;loc.scroll_into_view_if_needed();page.wait_for_timeout(30)
                b=loc.bounding_box();return (b['x']+b['width']/2,b['y']+b['height']/2)
            def y(page):return page.evaluate('document.scrollingElement.scrollTop')
            def diag(page):return page.evaluate('HemmaTouchScroll.diagnostics()')
            def check(name,fn,**options):
                ctx,page,errors=make(**options)
                try:
                    detail=fn(page) or {}
                    assert not errors, errors
                    reports.append(dict(name=name,passed=True,detail=detail))
                    print('PASS '+name,flush=True)
                except Exception as exc:
                    reports.append(dict(name=name,passed=False,error=str(exc)))
                    print('FAIL '+name+': '+str(exc),flush=True)
                    page.screenshot(path=str(RESULTS/('failure-'+str(len(reports))+'.png')))
                    traceback.print_exc()
                finally:ctx.close()

            def no_bars(page):
                d=diag(page);assert d['maxScrollY']>100,d
                assert d['scrollbarWidth']=='none' and d['scrollbarGutterPx']==0,d
                props=page.evaluate('''() => [...document.querySelectorAll('*')].filter(e=>e.scrollHeight>e.clientHeight+2&&['auto','scroll'].includes(getComputedStyle(e).overflowY)).map(e=>getComputedStyle(e).scrollbarWidth)''')
                assert all(x=='none' for x in props),props
                return d
            for view in ('home','user','badges'):
                check('no scrollbars on '+view,no_bars,view=view)

            def mouse_background(page):
                before=y(page);drag(page);after=y(page)
                assert after-before>300,(before,after);return diag(page)
            for view in ('home','user','badges'):
                check('mouse-emulated finger drags background: '+view,mouse_background,view=view)

            def native_background(page):
                before=y(page);drag(page,touch=True);page.wait_for_timeout(150);after=y(page)
                assert after-before>180,(before,after);assert diag(page)['pointerType']=='touch';return diag(page)
            for view in ('home','user','badges'):
                check('native touch drags background: '+view,native_background,view=view,touch=True)

            def card_drag(page,touch=False):
                start=pos(page,'.profile-card');before=y(page)
                drag(page,start,(start[0],max(80,start[1]-230)),touch=touch)
                page.wait_for_timeout(80)
                assert y(page)>before+70,(before,y(page))
                assert page.evaluate('__nav.length')==0
                assert page.evaluate('getSelection().toString()')==''
                return diag(page)
            check('mouse drag over profile never opens link',card_drag)
            check('native drag over profile never opens link',lambda p:card_drag(p,True),touch=True)

            def task_drag(page,touch=False):
                start=pos(page,'.task-check');before=y(page)
                drag(page,start,(start[0],max(70,start[1]-170)),touch=touch)
                page.wait_for_timeout(80)
                assert y(page)>before+60,(before,y(page))
                assert page.evaluate('__posts.length')==0
                return diag(page)
            check('mouse drag on completion button never completes task',task_drag,view='user')
            check('native drag on completion button never completes task',lambda p:task_drag(p,True),view='user',touch=True)

            def single_tap(page,touch=False):
                start=pos(page,'.profile-card')
                if touch:page.touchscreen.tap(*start)
                else:page.mouse.click(*start)
                assert page.evaluate('__nav.length')==1
            check('profile mouse tap still activates',single_tap)
            check('profile native tap still activates',lambda p:single_tap(p,True),touch=True)

            def immediate_tap(page):
                start=pos(page,'.profile-card');drag(page,start,(start[0],start[1]-150))
                # No artificial delay beyond locating the now-visible card.
                target=page.locator('.profile-card').nth(4)
                target.click()
                assert page.evaluate('__nav.length')==1
            check('fresh tap immediately after drag is not swallowed',immediate_tap)

            def jitter(page):
                start=pos(page,'.profile-card');drag(page,start,(start[0]+2,start[1]-3),steps=2)
                assert page.evaluate('__nav.length')==1
            check('tiny finger movement remains a tap',jitter)

            def down(page):
                page.evaluate('window.scrollTo(0,600)');page.wait_for_timeout(50)
                before=y(page);drag(page,(16,240),(16,580))
                assert y(page)<before-250
            check('drag downward scrolls back up',down)

            def edge(page):
                page.evaluate('window.scrollTo(0,document.body.scrollHeight)');page.wait_for_timeout(40)
                before=y(page);drag(page)
                assert y(page)==before
                assert page.evaluate('__nav.length')==0
                drag(page,(16,240),(16,590))
                assert y(page)<before-250
            check('bottom boundary stops and reverses correctly',edge)

            def wheel(page):
                page.mouse.move(20,500);page.mouse.wheel(0,380);page.wait_for_timeout(200)
                assert y(page)>250
            check('mouse wheel remains usable',wheel)

            def keyboard(page):
                page.locator('.profile-card').first.focus();page.keyboard.press('Enter')
                assert page.evaluate('__nav.length')==1
            check('keyboard Enter still activates links',keyboard)

            def inertia(page):
                drag(page,(15,640),(15,320),steps=8,wait=13)
                end=y(page);page.wait_for_timeout(140);after=y(page)
                assert after>end+20,(end,after)
                page.mouse.move(15,450);page.mouse.down();stop=y(page);page.wait_for_timeout(150)
                assert abs(y(page)-stop)<2
                page.mouse.up();return dict(atRelease=end,after140ms=after)
            check('mouse momentum glides then stops on new contact',inertia,motion='no-preference')

            def reduced(page):
                drag(page);end=y(page);page.wait_for_timeout(250);assert y(page)==end
            check('reduced motion disables simulated momentum',reduced)

            def nested(page):
                page.evaluate('''() => {
                    const box=document.createElement('div');box.id='nested';box.style.cssText='position:fixed;left:200px;top:200px;width:300px;height:230px;overflow:auto;background:#ddd;z-index:20';
                    const inner=document.createElement('div');inner.style.height='800px';inner.textContent='Nested test';box.append(inner);document.body.append(box);
                }''')
                drag(page,(250,400),(250,240));assert page.locator('#nested').evaluate('e=>e.scrollTop')>100
                assert y(page)==0
                page.locator('#nested').evaluate('e=>e.scrollTop=e.scrollHeight');drag(page,(250,400),(250,240))
                assert y(page)>100
            check('inner scroll list and parent boundary chaining',nested)

            def dynamic(page):
                store.save_user('Ny profil '+str(len(store.users())))
                page.wait_for_timeout(3300)
                count=page.locator('.profile-card').count();assert count>=17,count
                start=pos(page,'.profile-card');before=y(page);drag(page,start,(start[0],start[1]-180))
                assert y(page)>before+70 and page.evaluate('__nav.length')==0
            check('live-refreshed profile cards are also draggable',dynamic)

            def freeze(page):
                start=pos(page,'.profile-card');drag(page,start,(start[0],start[1]-170),release=False)
                count=page.locator('.profile-card').count();store.save_user('Under drag '+str(count))
                page.wait_for_timeout(3500);assert page.locator('.profile-card').count()==count
                page.mouse.up();page.wait_for_timeout(3600);assert page.locator('.profile-card').count()>count
            check('live updates wait until finger is released',freeze)

            def saver(page):
                page.locator('#preview-saver').click();assert page.locator('#screensaver').is_visible()
                page.mouse.click(500,400);page.wait_for_timeout(80)
                assert page.locator('#screensaver').is_hidden() and page.evaluate('__nav.length')==0
                page.locator('.profile-card').first.click();assert page.evaluate('__nav.length')==1
            check('screensaver wake consumes only the wake gesture',saver)

            def admin_clean(page):
                assert page.evaluate('typeof HemmaTouchScroll')=='undefined'
                assert page.locator('html').get_attribute('class') is None
                assert page.evaluate("getComputedStyle(document.documentElement).scrollbarWidth")!='none'
                page.locator('input[name="house_name"]').fill('Testfamiljen')
                assert page.locator('input[name="house_name"]').input_value()=='Testfamiljen'
                return dict(touchModuleLoaded=False)
            check('mobile admin has no kiosk CSS or drag handlers',admin_clean,view='admin',touch=True,width=390,height=844)

            def admin_touch(page):
                assert page.evaluate('typeof HemmaTouchScroll')=='undefined'
                before=y(page);drag(page,(8,740),(8,200),touch=True);page.wait_for_timeout(100)
                assert y(page)>before+100
            check('mobile admin keeps normal native touch scroll',admin_touch,view='admin',touch=True,width=390,height=844)

            def admin_select(page):
                field=page.locator('input[name="house_name"]');field.fill('Text kan markeras');field.select_text()
                assert field.evaluate('e=>e.selectionEnd-e.selectionStart')==17
            check('admin text selection remains available',admin_select,view='admin',width=390,height=844)

            def login(page):
                assert page.evaluate('typeof HemmaTouchScroll')=='undefined'
                assert not page.locator('html').get_attribute('class')
            check('login also excluded from kiosk mode',login,view='login',touch=True,width=390,height=844)

            def test_screen(page):
                start=pos(page,'#test-card');drag(page,start,(start[0],start[1]-150))
                assert y(page)>100 and page.locator('#click-state').inner_text()=='Tryck: 0'
                page.locator('#test-button').click();page.wait_for_timeout(50)
                assert page.locator('#click-state').inner_text()=='Tryck: 1'
                assert diag(page)['pointerType']=='mouse'
            check('built-in diagnostic distinguishes dragging from tapping',test_screen,view='test')


            def complete_tap(page,touch=False):
                start=pos(page,'.task-check')
                if touch:page.touchscreen.tap(*start)
                else:page.mouse.click(*start)
                page.wait_for_function('window.__posts.length === 1')
                page.wait_for_timeout(100)
                assert page.locator('#reward').is_visible()
                assert '/complete' in page.evaluate('__posts[0].path')
                page.locator('#reward-close').click()
                assert page.locator('#reward').is_hidden()
            check('normal mouse tap completes a task and shows reward',complete_tap,view='user')
            check('normal native tap completes a task and shows reward',lambda p:complete_tap(p,True),view='user',touch=True)

            def native_hold(page):
                c=page.context.new_cdp_session(page)
                c.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':15,'y':620,'id':1}]})
                for i in range(1,12):
                    c.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':15,'y':620-25*i,'id':1}]});page.wait_for_timeout(15)
                count=page.locator('.profile-card').count();store.save_user('Native hold '+str(count))
                page.wait_for_timeout(3500)
                assert page.locator('.profile-card').count()==count
                assert page.evaluate('HemmaTouchScroll.isBusy()')
                c.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});c.detach()
                page.wait_for_timeout(3600)
                assert page.locator('.profile-card').count()>count
            check('native finger held after scroll also pauses live updates',native_hold,touch=True)

            def bounds(page):
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                no_bars(page)
                page.screenshot(path=str(RESULTS/'touch-home-1280x720.png'))
            check('1280x720 layout fits without horizontal overflow',bounds)
            check('800x480 layout scrolls without side scrollbar',no_bars,view='user',width=800,height=480)

            ctx,page,_=make(view='test')
            page.screenshot(path=str(RESULTS/'touch-test-1280x720.png'))
            ctx.close()
            browser.close()
    result=dict(browser='Chromium',version='144.0.7559.96',method='Headless Chromium; real mouse and CDP touch input; local rendered templates; in-memory fetch adapter, not Flask',physical_pi_tested=False,results=reports,passed=sum(x['passed'] for x in reports),failed=sum(not x['passed'] for x in reports))
    (RESULTS/'touch-browser-results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(f"RESULT {result['passed']} passed; {result['failed']} failed",flush=True)
    raise SystemExit(bool(result['failed']))

if __name__=='__main__': main()

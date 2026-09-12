/* Optional voice controls. No scroll/drag handlers, no cloud or remote playback. */
(() => {
  'use strict';
  if (window.HemmaVoice54) return;
  const bootEl=document.getElementById('boot'); if(!bootEl)return;
  const boot=JSON.parse(bootEl.textContent);
  const admin=!!document.querySelector('[data-voice-admin]');
  if(boot.view!=='user'&&!admin)return;
  let config=null, engine=null, context=null, gain=null, source=null, finish=null;
  let generation=0, controller=null, busy=false, lastTask=null, requestBusy=false;
  const uid=boot.user_id;
  const status=(text)=>{
    document.querySelectorAll('[data-voice-status]').forEach(el=>el.textContent=text);
  };
  function stop(message='') {
    generation++;
    if(controller)controller.abort();controller=null;
    if(source){try{source.stop();}catch(_){}source=null;}
    if(finish){finish();finish=null;}
    busy=false;document.body.classList.remove('voice-playing');status(message);
  }
  function unlock() {
    const Audio=window.AudioContext||window.webkitAudioContext;
    if(!Audio)throw new Error('Webbl\u00e4saren saknar ljudst\u00f6d. Prova Chromium eller Safari.');
    if(!context){context=new Audio();gain=context.createGain();gain.connect(context.destination);}
    return context.resume();
  }
  async function fetchConfig(id) {
    const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),6000);
    try {
      const r=await fetch(`/api/voice/profile/${id}`,{cache:'no-store',signal:ctrl.signal});
      if(!r.ok)throw new Error('Kunde inte l\u00e4sa profilens ljudinst\u00e4llning.');
      return await r.json();
    } finally {clearTimeout(timer);}
  }
  async function play(id,kind,tid,token,volume) {
    if(token!==generation)return;
    controller=new AbortController();const ctrl=controller;
    const timer=setTimeout(()=>ctrl.abort(),26000);
    let raw;
    try {
      const r=await fetch(`/api/voice/profile/${id}/audio`,{method:'POST',cache:'no-store',
        signal:ctrl.signal,headers:{'Content-Type':'application/json','X-CSRF-Token':boot.csrf},
        body:JSON.stringify({kind,task_id:tid})});
      if(!r.ok){const err=await r.json().catch(()=>({}));throw new Error(err.error||'Kunde inte skapa ljud.');}
      if(!r.headers.get('Content-Type')?.includes('audio/wav'))throw new Error('Ovantat ljudsvar. Ladda om sidan.');
      raw=await r.arrayBuffer();
    } finally {clearTimeout(timer);if(controller===ctrl)controller=null;}
    if(token!==generation)return;
    const buffer=await context.decodeAudioData(raw);
    if(token!==generation)return;
    if(context.state!=='running')throw new Error('Tryck p\u00e5 L\u00e4s igen f\u00f6r att till\u00e5ta ljud.');
    gain.gain.value=Math.min(1,Math.max(0,Number(volume)/100));
    await new Promise(resolve=>{
      finish=resolve;source=context.createBufferSource();source.buffer=buffer;source.connect(gain);
      source.onended=()=>{source=null;finish=null;resolve();};source.start();
    });
  }
  async function speak(id,kind,ids=[]) {
    stop();const token=generation;
    // Called synchronously from a click/submit before any network awaits.
    let resumed;
    try {resumed=unlock();} catch(e){status(e.message);return;}
    busy=true;document.body.classList.add('voice-playing');status('F\u00f6rbereder uppl\u00e4sning\u2026');
    try {
      await resumed;
      const d=await fetchConfig(id);if(token!==generation)return;
      if(!d.settings.enabled)throw new Error('Uppl\u00e4sning \u00e4r avst\u00e4ngd f\u00f6r den h\u00e4r profilen.');
      if(!d.engine.ready)throw new Error(d.engine.message);
      if(d.settings.volume===0)throw new Error('Profilens volym \u00e4r 0. H\u00f6j den i admin.');
      if(kind==='all')ids=d.pending_ids;
      if(kind==='all'&&!ids.length){status('Inga uppgifter kvar att l\u00e4sa.');return;}
      const queue=(kind==='all'||kind==='task'||kind==='reward')?ids:[null];
      for(let i=0;i<queue.length&&token===generation;i++){
        status(queue.length>1?`L\u00e4ser uppgift ${i+1} av ${queue.length}\u2026`:'L\u00e4ser upp\u2026');
        await play(id,kind==='all'?'task':kind,queue[i],token,d.settings.volume);
      }
      if(token===generation)status('Uppl\u00e4sningen \u00e4r klar.');
    } catch(e){if(token===generation)status(e.name==='AbortError'?'Pi:n svarade inte i tid. Tryck L\u00e4s f\u00f6r att prova igen.':e.message);}
    finally {if(token===generation){busy=false;document.body.classList.remove('voice-playing');}}
  }
  function button(text,kind){const b=document.createElement('button');b.type='button';b.className='button secondary voice-button';b.dataset.voiceAction=kind;b.textContent=text;return b;}
  function mount() {
    if(admin||!config)return;
    if(!config.enabled){document.querySelectorAll('[data-voice-toolbar],[data-voice-action="task"]').forEach(el=>el.remove());return;}
    const hero=document.querySelector('.person-hero');if(!hero)return;
    if(!document.querySelector('[data-voice-toolbar]')){
      const bar=document.createElement('section');bar.dataset.voiceToolbar='';bar.className='voice-toolbar';bar.setAttribute('aria-label','Uppl\u00e4sning');
      bar.append(button('L\u00e4s mina uppgifter','all'),button('Stoppa','stop'));
      const s=document.createElement('span');s.dataset.voiceStatus='';s.setAttribute('role','status');s.textContent=engine?.ready?'Tryck f\u00f6r att lyssna.':engine?.message||'';bar.append(s);hero.after(bar);
    }
    document.querySelectorAll('form[data-task]').forEach(row=>{
      if(row.querySelector('[data-voice-action="task"]'))return;
      const b=button('L\u00e4s','task');b.dataset.voiceTask=row.dataset.task;
      b.setAttribute('aria-label','L\u00e4s upp: '+(row.querySelector('.task-copy strong')?.textContent||'uppgiften'));
      row.append(b);
    });
  }
  async function refresh() {
    if(admin||requestBusy||document.hidden)return;
    requestBusy=true;
    try {
      const d=await fetchConfig(uid);const old=config;config=d.settings;engine=d.engine;
      if(old&&old.enabled&&!config.enabled)stop();
      if(old&&busy&&(old.speed!==config.speed||old.volume!==config.volume))stop('Ljudinst\u00e4llningen \u00e4ndrades. Tryck L\u00e4s igen.');
      mount();
    } catch(_){} finally {requestBusy=false;}
  }
  document.addEventListener('click',e=>{
    const b=e.target.closest('[data-voice-action]');if(!b)return;
    if(e.defaultPrevented)return;
    const action=b.dataset.voiceAction;
    if(action==='stop'){stop('Stoppad.');return;}
    const id=Number(b.dataset.voiceUser||uid);
    speak(id,action,action==='task'?[Number(b.dataset.voiceTask)]:[]);
  });
  // Capture real submit intent, not pointer drags. Core app still owns completion.
  document.addEventListener('submit',e=>{
    const form=e.target.closest('form[data-task]');
    if(!form||!config?.enabled||!config.rewards)return;
    stop();lastTask=Number(form.dataset.task);
    try{unlock().catch(()=>{});}catch(_){}
  },true);
  const reward=document.getElementById('reward');
  if(reward)new MutationObserver(()=>{
    if(!reward.hidden&&lastTask&&config?.enabled&&config.rewards){const tid=lastTask;lastTask=null;speak(uid,'reward',[tid]);}
  }).observe(reward,{attributes:true,attributeFilter:['hidden']});
  // Live HTML updates keep controls without replacing the existing touch engine.
  const live=document.querySelector('[data-live]');
  if(live)new MutationObserver(mount).observe(live,{childList:true,subtree:true});
  const saver=document.getElementById('screensaver');
  if(saver)new MutationObserver(()=>{if(!saver.hidden)stop();}).observe(saver,{attributes:true,attributeFilter:['hidden']});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();else refresh();});
  window.addEventListener('pagehide',()=>stop());
  window.HemmaVoice54={version:'5.4.0',stop,get busy(){return busy;}};
  refresh();if(!admin)setInterval(refresh,12000);
})();

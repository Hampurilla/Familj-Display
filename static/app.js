/* No framework, no remote assets, no optimistic duplicate toggles. */
(() => {
  'use strict';
  const boot = JSON.parse(document.getElementById('boot').textContent);
  const isAdmin = ['admin','login'].includes(boot.view);
  let knownVersion = boot.version, offset = Date.parse(boot.now) - Date.now();
  let config = boot.settings, busy = false, rewardActive = false, saverActive = false;
  let statePromise = null, weatherValue = null, saver = null, toastTimer = null;
  let lastInput = 0, suppressUntil = 0, rewardResolve = null;
  const read = (key, fallback) => { try { return sessionStorage.getItem(key) ?? fallback; } catch (_) { return fallback; } };
  const write = (key, value) => { try { sessionStorage.setItem(key, String(value)); } catch (_) {} };
  let lastActivity = Number(read('hemma-activity',Date.now()));
  if (!Number.isFinite(lastActivity) || lastActivity > Date.now()) lastActivity = Date.now();
  const now = () => new Date(Date.now() + offset);
  const svTime = new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Stockholm',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
  const svDate = new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Stockholm',weekday:'long',day:'numeric',month:'long'});
  const svgNS = 'http://www.w3.org/2000/svg';
  function icon(name, cls='') {
    const svg=document.createElementNS(svgNS,'svg'), use=document.createElementNS(svgNS,'use');
    svg.setAttribute('class','icon '+cls); svg.setAttribute('aria-hidden','true');
    use.setAttribute('href',`#${name}`);svg.appendChild(use);return svg;
  }
  function el(tag,cls,text) { const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n; }
  function toast(text) { const box=document.getElementById('toast');if(!box)return;box.textContent=text;box.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>box.hidden=true,6500); }
  window.Hemma={boot,toast,icon};
  function setOnline(ok) {
    const node=document.getElementById('connection');if(!node)return;
    node.classList.toggle('offline',!ok);node.querySelector('span').textContent=ok?'Lokalt & i synk':'Ingen kontakt med Pi:n';
  }
  async function api(path,options={}) {
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),7000);
    try {
      const res=await fetch(path,{...options,cache:'no-store',signal:controller.signal});
      if(!res.ok){const err=await res.json().catch(()=>({}));const e=new Error(err.error||`Serverfel (${res.status})`);e.status=res.status;throw e;}
      return await res.json();
    } finally {clearTimeout(timer);}
  }
  function updateClock() {
    const value=svTime.format(now()), hour=Number(value.slice(0,2));
    document.querySelectorAll('[data-clock]').forEach(n=>n.textContent=value);
    document.querySelectorAll('[data-date]').forEach(n=>n.textContent=svDate.format(now()));
    const greeting=hour<5?'God natt':hour<11?'God morgon':hour<17?'God eftermiddag':'God kv\u00e4ll';
    document.querySelectorAll('[data-greeting]').forEach(n=>n.textContent=greeting);
  }
  function applyUI() {
    updateClock();
    document.body.classList.toggle('focus-mode',boot.view==='user'&&read('hemma-focus-'+boot.user_id,'0')==='1');
    const f=document.querySelector('.focus-toggle');if(f)f.setAttribute('aria-pressed',document.body.classList.contains('focus-mode'));
    filterBadges(read('hemma-badge-filter','all'));
    renderWeather(weatherValue);
  }
  function filterBadges(filter) {
    document.querySelectorAll('[data-badge-filter]').forEach(b=>{const on=b.dataset.badgeFilter===filter;b.classList.toggle('selected',on);b.setAttribute('aria-pressed',on);});
    document.querySelectorAll('.badge-tile').forEach(b=>b.hidden=filter==='owned'?b.dataset.owned!=='1':filter!=='all'&&b.dataset.rarity!==filter);
  }
  function replaceLive(html) {
    if(typeof html!=='string')return;
    const main=document.querySelector('[data-live]');if(!main)return;
    const details=[...main.querySelectorAll('details[data-remember]')].filter(n=>n.open).map(n=>n.dataset.remember);
    const scroll=window.scrollY;
    main.innerHTML=html;
    main.querySelectorAll('details[data-remember]').forEach(n=>n.open=details.includes(n.dataset.remember));
    applyUI();window.scrollTo(0,scroll);
  }
  async function refreshState(force=false) {
    if(statePromise)return statePromise;
    if(!isAdmin && window.HemmaTouchScroll?.isBusy())return;
    if((busy||rewardActive)&&!force)return;
    if(!force && Date.now()-lastInput<800)return;
    statePromise=(async()=>{
      try{
        const params=new URLSearchParams({view:boot.view,since:force?'-1':String(knownVersion),release:boot.release});
        if(boot.user_id)params.set('user_id',String(boot.user_id));
        const d=await api('/api/state?'+params);setOnline(true);
        offset=Date.parse(d.now)-Date.now();config=d.settings;
        if(d.release!==boot.release){
          if(isAdmin){document.getElementById('admin-update-notice')?.removeAttribute('hidden');return;}
          if(!saverActive&&!busy&&!rewardActive){write('hemma-activity',lastActivity);location.reload();return;}
        }
        if(isAdmin){if(d.version!==knownVersion)document.getElementById('admin-update-notice')?.removeAttribute('hidden');}
        else if(!busy&&!rewardActive) {
          if(window.HemmaTouchScroll?.isBusy())return;
          replaceLive(d.html);
        }
        knownVersion=d.version;
        evaluateIdle();
      }catch(e){
        if(e.status===404&&!isAdmin&&boot.view!=='home'){location.assign('/');return;}
        setOnline(false);
      }finally{statePromise=null;}
    })();
    return statePromise;
  }
  function renderWeather(d) {
    const card=document.querySelector('[data-weather]');if(!card||!d)return;
    card.replaceChildren();
    const label=el('div','weather-label');label.append(icon('pin'),el('span','',d.name||config.weather_name));card.appendChild(label);
    if(!d.ok){const line=el('div','weather-skeleton');line.append(icon('partly'),el('strong','','\u2014\u00b0'),el('p','',d.loading?'H\u00e4mtar prognosen\u2026':'V\u00e4dret tar en paus. Allt annat fungerar.'));card.appendChild(line);return;}
    const row=el('div','weather-main'), current=el('div','weather-now'),copy=el('div','weather-copy');
    copy.append(el('strong','',d.text),el('small','',`K\u00e4nns som ${d.feels}\u00b0`),el('small','',`Vind ${String(d.wind).replace('.',',')} m/s`));
    current.append(icon(d.icon,'weather-art'),el('strong','weather-number',d.temp+'\u00b0'),copy);row.appendChild(current);
    const forecast=el('div','forecast');(d.days||[]).forEach(day=>{const col=el('div','forecast-day');col.append(el('span','',day.label),icon(day.icon),el('strong','',day.high+'\u00b0'),el('small','',day.low+'\u00b0'));forecast.appendChild(col);});
    row.appendChild(forecast);card.appendChild(row);
    const bottom=el('div','weather-bottom');
    let stamp=d.fetched_at?svTime.format(new Date(d.fetched_at*1000)):'';
    if(d.stale&&d.fetched_at)stamp=svDate.format(new Date(d.fetched_at*1000))+' '+stamp;
    bottom.appendChild(el('span','',d.stale?'Sparad prognos \u00b7 '+stamp:'Uppdaterat '+stamp));
    const credit=el('a','','V\u00e4der: Open-Meteo');credit.href='https://open-meteo.com/';credit.target='_blank';credit.rel='noopener noreferrer';bottom.appendChild(credit);card.appendChild(bottom);
  }
  async function loadWeather() {
    if(!document.querySelector('[data-weather]'))return;
    try{weatherValue=await api('/api/weather');renderWeather(weatherValue);}catch(_){if(!weatherValue)renderWeather({ok:false,name:config.weather_name});}
  }
  function closeReward(){
    const box=document.getElementById('reward');if(box)box.hidden=true;
    document.body.classList.remove('modal-open');rewardActive=false;
    if(rewardResolve){const resolve=rewardResolve;rewardResolve=null;resolve();}
  }
  function showReward(r){
    if(!r)return Promise.resolve();
    const box=document.getElementById('reward');if(!box)return Promise.resolve();
    document.getElementById('reward-emoji').textContent=r.emoji;
    document.getElementById('reward-message').textContent=r.message;
    document.getElementById('reward-name').textContent=r.name+(r.new?'':' \u00b7 '+r.count+' i samlingen');
    document.getElementById('reward-new').textContent=r.new?'Ett nytt litet fynd!':'En liten seger';
    const rarity=document.getElementById('reward-rarity');rarity.dataset.rarity=r.rarity;rarity.textContent={common:'Vanligt',uncommon:'Ovanligt',rare:'S\u00e4llsynt',legendary:'Legendariskt'}[r.rarity];
    document.getElementById('reward-points').textContent=`+${r.points} po\u00e4ng till dagens framsteg`;
    rewardActive=true;box.hidden=false;document.body.classList.add('modal-open');document.getElementById('reward-close').focus();
    return new Promise(resolve=>{rewardResolve=resolve;setTimeout(closeReward,3300);});
  }
  document.addEventListener('submit',async e=>{
    const form=e.target.closest('form[data-task]');if(!form)return;
    e.preventDefault();if(busy)return;
    busy=true;const button=form.querySelector('.task-check');button.disabled=true;
    const desired=form.querySelector('[name=completed]').value==='1';
    try{
      const d=await api(`/api/tasks/${form.dataset.task}/complete`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':boot.csrf},body:JSON.stringify({completed:desired})});
      form.classList.toggle('is-done',d.completed);
      await showReward(d.reward);setOnline(true);
    }catch(error){toast(error.status?error.message:'Ingen bekr\u00e4ftelse fr\u00e5n Pi:n. Listan kontrolleras n\u00e4r kontakten kommer tillbaka.');}
    finally{busy=false;if(button.isConnected)button.disabled=false;await refreshState(true);}
  });
  document.addEventListener('click',e=>{
    if(e.target.closest('#reward-close'))closeReward();
    const f=e.target.closest('.focus-toggle');if(f){const on=!document.body.classList.contains('focus-mode');write('hemma-focus-'+boot.user_id,on?'1':'0');applyUI();}
    const b=e.target.closest('[data-badge-filter]');if(b){write('hemma-badge-filter',b.dataset.badgeFilter);filterBadges(b.dataset.badgeFilter);}
    if(e.target.closest('#preview-saver'))showSaver();
  });
  function nightWindow(){
    if(config.night_enabled!=='1')return false;
    const parse=value=>{const pair=String(value).split(':').map(Number);return pair[0]*60+pair[1];};
    const n=parse(svTime.format(now())),a=parse(config.night_start),b=parse(config.night_end);
    if(!Number.isFinite(a)||!Number.isFinite(b)||a===b)return false;
    return a<b?n>=a&&n<b:n>=a||n<b;
  }
  function showSaver(){
    const overlay=document.getElementById('screensaver');if(!overlay||busy||rewardActive)return;
    saverActive=true;overlay.hidden=false;
    const black=nightWindow();overlay.classList.toggle('is-night',black);
    if(!saver&&window.HemmaSaver)saver=new window.HemmaSaver(document.getElementById('saver-canvas'),()=>svTime.format(now()));
    if(black)saver?.stop();else saver?.start();
  }
  function wake(){
    const overlay=document.getElementById('screensaver');if(overlay)overlay.hidden=true;
    saver?.stop();saverActive=false;lastActivity=Date.now();write('hemma-activity',lastActivity);
    if(boot.view!=='home')location.assign('/');else refreshState(true);
  }
  function evaluateIdle(){
    if(isAdmin||busy||rewardActive||window.HemmaTouchScroll?.isBusy()||!document.getElementById('screensaver'))return;
    if(saverActive){
      const black=nightWindow();const overlay=document.getElementById('screensaver');
      if(black!==overlay.classList.contains('is-night')){overlay.classList.toggle('is-night',black);if(black)saver?.stop();else saver?.start();}
      return;
    }
    const mins=Math.min(120,Math.max(1,Number(config.idle_minutes)||15));
    if(Date.now()-lastActivity>=mins*60000&&(nightWindow()||config.screensaver_enabled==='1'))showSaver();
  }
  let pointerStart=null;
  window.addEventListener('pointerdown',e=>{
    if(saverActive){e.preventDefault();e.stopImmediatePropagation();suppressUntil=Date.now()+700;wake();return;}
    if(!isAdmin)suppressUntil=0;
    pointerStart=(!window.HemmaTouchScroll)?{x:e.clientX,y:e.clientY}:null;
    lastActivity=lastInput=Date.now();write('hemma-activity',lastActivity);
  },true);
  window.addEventListener('pointermove',e=>{
    if(!saverActive&&(e.pointerType==='mouse'||e.buttons)){lastActivity=Date.now();write('hemma-activity',lastActivity);}
  },{passive:true});
  window.addEventListener('pointerup',e=>{if(pointerStart&&Math.hypot(e.clientX-pointerStart.x,e.clientY-pointerStart.y)>12)suppressUntil=Date.now()+350;pointerStart=null;},true);
  window.addEventListener('click',e=>{if(Date.now()<suppressUntil){e.preventDefault();e.stopImmediatePropagation();}},true);
  window.addEventListener('keydown',e=>{
    if(saverActive){e.preventDefault();e.stopImmediatePropagation();suppressUntil=Date.now()+500;wake();return;}
    lastActivity=lastInput=Date.now();write('hemma-activity',lastActivity);
    if(rewardActive&&e.key==='Escape')closeReward();
    if(rewardActive&&e.key==='Tab'){e.preventDefault();document.getElementById('reward-close').focus();}
  },true);
  window.addEventListener('scroll',()=>{lastInput=Date.now();},{passive:true});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)saver?.stop();else{if(saverActive&&!nightWindow())saver?.start();refreshState();}});
  async function poll(){await refreshState();setTimeout(poll,boot.poll_ms||3000);}
  if(['home','user','badges'].includes(boot.view) && !window.HemmaTouchScroll) {
    toast('Touchmodulen saknas. Kontrollera att alla filer i Touch 5.2 har kopierats.');
  }
  applyUI();loadWeather();setTimeout(poll,1000);setInterval(updateClock,1000);setInterval(evaluateIdle,1000);
  setInterval(()=>{if(document.querySelector('[data-weather]'))loadWeather();},15000);
})();

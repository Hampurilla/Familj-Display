(() => {
 'use strict';if(!document.querySelector('[data-mobile54]'))return;
 const field=document.getElementById('mobile54-url'),feedback=document.getElementById('mobile54-feedback');
 const valid=url=>typeof url==='string'&&/^https:\/\/([a-z0-9-]+\.)+ts\.net\/admin$/.test(url);
 document.getElementById('mobile54-refresh').addEventListener('click',async e=>{
  e.target.disabled=true;const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),9000);
  try{
   const r=await fetch('/admin/mobile/status',{cache:'no-store',signal:ctrl.signal});
   if(r.redirected||!r.ok)throw new Error('Logga in i admin igen och ladda om sidan.');
   const d=await r.json();document.getElementById('mobile54-title').textContent=d.title;document.getElementById('mobile54-detail').textContent=d.detail;
   const safe=d.configured&&valid(d.url);field.value=safe?d.url:'';
   document.getElementById('mobile54-address').hidden=!safe;
   document.getElementById('mobile54-open').href=safe?d.url:'/admin';
   feedback.textContent=safe?'Spara den h\u00e4r adressen en g\u00e5ng. Samma l\u00e4nk hemma och borta.':'Adressen \u00e4r inte redo \u00e4n. F\u00f6lj guiden nedan.';
  }catch(err){feedback.textContent=err.name==='AbortError'?'Pi:n svarade inte i tid.':err.message;}
  finally{clearTimeout(timer);e.target.disabled=false;}
 });
 document.getElementById('mobile54-copy').addEventListener('click',async()=>{
  if(!valid(field.value))return;
  try{await navigator.clipboard.writeText(field.value);feedback.textContent='Kopierad. Spara i Safari p\u00e5 hemsk\u00e4rmen en g\u00e5ng.';}
  catch(_){field.focus();field.select();field.setSelectionRange(0,field.value.length);feedback.textContent='Adressen \u00e4r markerad. Kopiera den eller tryck \u00d6ppna r\u00e4tt adress.';}
 });
})();

/* Only /admin/remote. Does not intercept scroll, taps or existing forms. */
(() => {
 'use strict';
 const panel=document.querySelector('.remote-status'); if(!panel)return;
 const refresh=document.getElementById('remote-refresh');
 const feedback=document.getElementById('remote-feedback');
 const copy=document.getElementById('remote-copy');
 async function update(){
   refresh.disabled=true;
   const ctrl=new AbortController();const timer=setTimeout(()=>ctrl.abort(),9000);
   try{
     const response=await fetch('/admin/remote/status',{cache:'no-store',signal:ctrl.signal});
     if(response.redirected||response.status===401)throw new Error('Logga in i admin igen och ladda sedan om den h\u00e4r sidan.');
     if(!response.ok)throw new Error('Status kunde inte h\u00e4mtas. Prova igen.');
     const d=await response.json();
     panel.dataset.state=d.state;
     document.getElementById('remote-title').textContent=d.title;
     document.getElementById('remote-detail').textContent=d.detail;
     const valid=typeof d.url==='string'&&/^https:\/\/([a-z0-9-]+\.)+ts\.net\/admin$/.test(d.url);
     document.getElementById('remote-address').hidden=!valid;
     document.getElementById('remote-url').value=valid?d.url:'';
     document.getElementById('remote-open').href=valid?d.url:'/admin';
     document.getElementById('remote-check').textContent='Status kontrollerad '+new Date().toLocaleTimeString('sv-SE',{hour:'2-digit',minute:'2-digit'})+'. Prova \u00e4ven p\u00e5 mobildata.';
     feedback.textContent='';
   }catch(e){feedback.textContent=e.name==='AbortError'?'Pi:n svarade inte i tid. Din vanliga app p\u00e5verkas inte.':e.message;}
   finally{clearTimeout(timer);refresh.disabled=false;}
 }
 refresh.addEventListener('click',update);
 copy.addEventListener('click',async()=>{
   const field=document.getElementById('remote-url'); if(!field.value)return;
   try{
     if(!navigator.clipboard||!window.isSecureContext)throw new Error('no_clipboard');
     await navigator.clipboard.writeText(field.value);feedback.textContent='Adressen \u00e4r kopierad. Tailscale m\u00e5ste vara anslutet i mobilen.';
   }catch(_){field.focus();field.select();field.setSelectionRange(0,field.value.length);feedback.textContent='Adressen \u00e4r markerad. Tryck och h\u00e5ll f\u00f6r att kopiera, eller anv\u00e4nd Ctrl+C.';}
 });
})();

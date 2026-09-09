(() => {
  'use strict';
  const {toast,icon}=window.Hemma;
  let dirty=false;
  document.addEventListener('input',e=>{if(e.target.closest('form'))dirty=true;});
  document.addEventListener('change',e=>{if(e.target.closest('form'))dirty=true;});
  document.querySelectorAll('form').forEach(form=>form.addEventListener('submit',e=>{
    if(form.dataset.confirm&&!window.confirm(form.dataset.confirm)){e.preventDefault();return;}
    dirty=false;
    // Native navigation keeps server validation and downloads reliable.
    if(form.action.endsWith('/backup'))return;
    const b=e.submitter;if(b){b.disabled=true;setTimeout(()=>b.disabled=false,10000);}
  }));
  window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
  document.getElementById('admin-refresh')?.addEventListener('click',()=>{
    if(!dirty||window.confirm('Ladda om sidan? Osparade formul\u00e4r\u00e4ndringar f\u00f6rsvinner.')){dirty=false;location.reload();}
  });
  const mode=document.getElementById('task-mode');
  function syncMode(){if(!mode)return;document.getElementById('fixed-user-box').hidden=mode.value!=='fixed';document.getElementById('eligible-box').hidden=mode.value==='fixed';}
  mode?.addEventListener('change',syncMode);syncMode();
  const search=document.getElementById('location-search'),query=document.getElementById('location-query'),box=document.getElementById('location-results');
  async function searchPlace(){
    const q=query.value.trim();if(q.length<2){toast('Skriv minst tv\u00e5 bokst\u00e4ver.');return;}
    search.disabled=true;box.textContent='S\u00f6ker ort\u2026';
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),6500);
    try{
      const res=await fetch('/api/locations?q='+encodeURIComponent(q),{cache:'no-store',signal:controller.signal});const d=await res.json();
      if(!res.ok)throw new Error(d.error||'S\u00f6kningen misslyckades.');
      box.replaceChildren();if(!d.results.length){box.textContent='Ingen ort hittades. Prova ett annat namn.';return;}
      d.results.forEach(p=>{const b=document.createElement('button');b.type='button';b.className='location-option';const name=document.createElement('span'),region=document.createElement('small');name.textContent=p.name;region.textContent=[p.region,p.country].filter(Boolean).join(', ');b.append(name,region,icon('arrow'));
        b.addEventListener('click',()=>{document.getElementById('weather-name').value=p.name;document.getElementById('weather-lat').value=p.lat;document.getElementById('weather-lon').value=p.lon;box.textContent=p.name+' valt. Tryck Spara inst\u00e4llningar l\u00e4ngst ner.';dirty=true;});box.appendChild(b);});
    }catch(e){box.textContent=e.name==='AbortError'?'S\u00f6kningen tog f\u00f6r l\u00e5ng tid. Prova igen eller ange koordinater.':e.message;}
    finally{clearTimeout(timer);search.disabled=false;}
  }
  search?.addEventListener('click',searchPlace);
  query?.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();searchPlace();}});
})();

(() => {
  'use strict';
  let taps = 0;
  const type = document.getElementById('input-type');
  const draw = () => {
    if (!window.HemmaTouchScroll) { type.textContent='Touchmodulen kunde inte laddas.'; return; }
    const d=window.HemmaTouchScroll.diagnostics();
    const names={none:'Inget tryck \u00e4n',mouse:'Mus / musemulerad touch',touch:'Touch',pen:'Penna'};
    type.textContent=names[d.pointerType]||d.pointerType;
    document.getElementById('scroll-state').textContent=`Scroll: ${d.scrollY} av ${d.maxScrollY} px`;
    document.getElementById('click-state').textContent=`Tryck: ${taps}`;
    document.getElementById('bar-state').textContent=d.scrollbarGutterPx===0?'Ingen sid-scrollbar':'Scrollspalt: '+d.scrollbarGutterPx+' px';
  };
  ['test-card','test-button'].forEach(id=>document.getElementById(id).addEventListener('click',e=>{e.preventDefault();taps++;draw();}));
  draw();setInterval(draw,350);
})();

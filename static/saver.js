/* A small local 2D scene, not a streamed video. Stops drawing when hidden/night. */
(() => {
  'use strict';
  class HemmaSaver {
    constructor(canvas, clock) {
      this.canvas=canvas;this.ctx=canvas.getContext('2d',{alpha:false});this.clock=clock;
      this.running=false;this.frame=0;this.last=0;this.startTime=performance.now();
      this.reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      this.fps=this.reduced?6:20;this.w=0;this.h=0;
      this.stars=Array.from({length:42},(_,i)=>({x:((i*137.37)%1000)/1000,y:((i*67.17)%440)/1000,r:i%4===0?1.6:.85}));
      this.tick=this.tick.bind(this);
    }
    resize(){
      const w=window.innerWidth,h=window.innerHeight;
      if(w===this.w&&h===this.h)return;
      this.w=w;this.h=h;this.canvas.width=w;this.canvas.height=h;
      this.city=document.createElement('canvas');this.city.width=w+80;this.city.height=h;
      const c=this.city.getContext('2d');
      for(let i=0,x=0;x<w+80;i++,x+=45+(i%5)*13){
        const bh=45+(i*41)%110,bw=34+(i%4)*12,y=h*.64-bh;
        c.fillStyle=i%3===0?'#263c43':'#1b3037';c.fillRect(x,y,bw,bh);
        c.fillStyle='#799079';for(let j=0;j<3;j++)for(let k=0;k<Math.floor(bh/20);k++)if((j+k+i)%3===0)c.fillRect(x+7+j*9,y+11+k*18,3,5);
      }
    }
    start(){if(this.running)return;this.running=true;this.last=0;this.resize();this.frame=requestAnimationFrame(this.tick);}
    stop(){this.running=false;cancelAnimationFrame(this.frame);}
    tick(stamp){
      if(!this.running)return;
      this.frame=requestAnimationFrame(this.tick);if(stamp-this.last<1000/this.fps)return;
      this.last=stamp;this.resize();this.draw((stamp-this.startTime)/1000);
    }
    draw(t){
      const c=this.ctx,w=this.w,h=this.h;
      c.fillStyle='#10242d';c.fillRect(0,0,w,h);
      // Very slow drift means clock, horizon and skyline do not remain fixed.
      const drift=Math.sin(t/37)*13,dy=Math.cos(t/43)*8;
      c.save();c.translate(drift,dy);
      const glow=c.createRadialGradient(w*.67,h*.3,0,w*.67,h*.3,w*.66);
      glow.addColorStop(0,'#294650');glow.addColorStop(1,'#10242d');c.fillStyle=glow;c.fillRect(-20,-20,w+40,h+40);
      for(const s of this.stars){const sx=(s.x*w+t*1.5)%(w+20);c.fillStyle='#aebcac';c.globalAlpha=.3+.3*Math.sin(t/4+s.x*20);c.beginPath();c.arc(sx,s.y*h,s.r,0,Math.PI*2);c.fill();}c.globalAlpha=1;
      c.fillStyle='#d3d5b5';c.beginPath();c.arc(w*.78,h*.2,22,0,Math.PI*2);c.fill();c.fillStyle='#28434d';c.beginPath();c.arc(w*.78-8,h*.2-7,21,0,Math.PI*2);c.fill();
      c.drawImage(this.city,-30+Math.sin(t/80)*15,0);
      c.fillStyle='#213b3e';c.beginPath();c.moveTo(-20,h*.68);c.bezierCurveTo(w*.2,h*.54,w*.45,h*.71,w*.62,h*.61);c.lineTo(w+30,h*.57);c.lineTo(w+30,h+30);c.lineTo(-20,h+30);c.fill();
      c.fillStyle='#132a30';c.beginPath();c.moveTo(-20,h*.78);c.bezierCurveTo(w*.35,h*.59,w*.7,h*.79,w+30,h*.68);c.lineTo(w+30,h+30);c.lineTo(-20,h+30);c.fill();
      c.strokeStyle='#536257';c.lineWidth=1;c.setLineDash([12,24]);c.beginPath();c.moveTo(-20,h*.79);c.lineTo(w+30,h*.79);c.stroke();c.setLineDash([]);
      this.car(((t*37)%(w+180))-90,h*.77,'#cdb187',false);
      this.car(w+90-((t*29+200)%(w+180)),h*.82,'#a5b9b5',true);
      this.car(((t*23+w*.48)%(w+180))-90,h*.77,'#8ea581',false);
      const planeX=((t*19)%(w+200))-100,planeY=h*.27+Math.sin(t/13)*h*.02;
      c.strokeStyle='#9fae9e';c.lineWidth=2;c.beginPath();c.moveTo(planeX-13,planeY);c.lineTo(planeX+14,planeY);c.moveTo(planeX,planeY);c.lineTo(planeX-8,planeY-9);c.moveTo(planeX,planeY);c.lineTo(planeX-8,planeY+9);c.stroke();
      const cx=w*.35+Math.sin(t/61)*w*.08,cy=h*.32+Math.cos(t/71)*h*.035;
      c.textAlign='center';c.fillStyle='#dce3cb';c.font=`300 ${Math.max(40,Math.min(81,w*.065))}px Arial`;c.fillText(this.clock(),cx,cy);
      c.fillStyle='#93a695';c.font=`${w<600?10:12}px Arial`;c.fillText('EN LITEN PAUS HEMMA',cx,cy+29);c.fillText('Tryck var som helst f\u00f6r att v\u00e4cka',cx,cy+52);
      c.restore();
    }
    car(x,y,color,reverse){
      const c=this.ctx;c.save();c.translate(x,y);if(reverse)c.scale(-1,1);
      c.fillStyle=color;c.beginPath();c.roundRect(-15,-8,30,9,3);c.fill();c.beginPath();c.moveTo(-8,-8);c.lineTo(-3,-14);c.lineTo(7,-14);c.lineTo(12,-8);c.closePath();c.fill();c.fillStyle='#203c43';c.fillRect(-2,-13,8,4);
      c.fillStyle='#091c21';for(const xx of [-9,9]){c.beginPath();c.arc(xx,2,3,0,Math.PI*2);c.fill();}c.fillStyle='#e9d7a0';c.fillRect(13,-6,3,3);c.restore();
    }
  }
  window.HemmaSaver=HemmaSaver;
})();

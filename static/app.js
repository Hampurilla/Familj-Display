let knownVersion=null;
let rewardInProgress=false;

function getGreeting(){
  const h=new Date().getHours();
  if(h<10)return "God morgon ☀️";
  if(h<17)return "Hej 👋";
  if(h<22)return "God kväll 🌙";
  return "Kvällsläge ✨";
}

function applyLivingRoomExtras(){
  const title=document.querySelector("h1");
  if(title && !document.querySelector(".living-greeting")){
    const g=document.createElement("div");
    g.className="living-greeting";
    g.textContent=getGreeting();
    title.parentNode.insertBefore(g,title);
  }

  const dash=document.querySelector(".dashboard-strip");
  if(dash && !document.querySelector(".living-strip")){
    const strip=document.createElement("div");
    strip.className="living-strip";
    strip.innerHTML='<span><span class="living-dot"></span><strong>Hemma idag</strong></span><span>En sak i taget</span>';
    dash.parentNode.insertBefore(strip,dash);
  }

  const empty=document.querySelector(".empty");
  if(empty && /klart|inga uppgifter/i.test(empty.textContent) && !document.querySelector(".complete-soft")){
    const done=document.createElement("div");
    done.className="complete-soft";
    done.textContent="✨ Bra jobbat — resten av dagen kan kännas lite lättare.";
    empty.appendChild(done);
  }
}

async function checkForUpdates(){
  if(rewardInProgress)return;
  try{
    const r=await fetch("/api/version",{cache:"no-store"});
    const d=await r.json();
    if(knownVersion===null){knownVersion=d.version;return}
    if(d.version!==knownVersion){
      const a=document.activeElement;
      const typing=a&&["INPUT","SELECT","TEXTAREA"].includes(a.tagName);
      if(!typing)location.reload();
    }
  }catch(_){}
}

function updateClock(){
  const now=new Date();
  const c=document.getElementById("clock");
  const d=document.getElementById("date");
  if(c)c.textContent=now.toLocaleTimeString("sv-SE",{hour:"2-digit",minute:"2-digit"});
  if(d)d.textContent=now.toLocaleDateString("sv-SE",{weekday:"long",day:"numeric",month:"long"});
  const g=document.querySelector(".living-greeting");
  if(g)g.textContent=getGreeting();
}

async function loadWeather(){
  const card=document.getElementById("weatherCard");
  if(!card)return;
  try{
    const r=await fetch("/api/weather",{cache:"no-store"});
    const data=await r.json();
    if(!data.ok)throw 0;
    const icon=document.getElementById("weatherIcon");
    const temp=document.getElementById("weatherTemp");
    const text=document.getElementById("weatherText");
    const place=document.getElementById("weatherPlace");
    if(icon)icon.textContent=data.icon;
    if(temp)temp.textContent=`${data.temp}°`;
    if(text)text.textContent=`${data.text} · känns ${data.feels}°`;
    if(place)place.textContent=data.name;
    const forecast=document.getElementById("forecast");
    if(forecast)forecast.innerHTML=data.days.map(day=>`
      <div class="forecast-day">
        <span>${day.label}</span>
        <strong>${day.icon} ${day.max}°</strong>
        <small>${day.min}°</small>
      </div>`).join("");
  }catch(_){
    const text=document.getElementById("weatherText");
    if(text)text.textContent="Väder ej tillgängligt";
  }
}

function showReward(reward){
  if(!reward)return Promise.resolve();
  rewardInProgress=true;
  const o=document.getElementById("rewardOverlay");
  if(!o){rewardInProgress=false;return Promise.resolve()}
  const e=document.getElementById("rewardEmoji");
  const m=document.getElementById("rewardMessage");
  const p=document.getElementById("rewardPoints");
  if(e)e.textContent=reward.emoji;
  if(m)m.textContent=reward.message;
  if(p)p.textContent=`+${reward.points} poäng`;
  o.classList.add("show");
  o.setAttribute("aria-hidden","false");
  return new Promise(res=>setTimeout(()=>{
    o.classList.remove("show");
    o.setAttribute("aria-hidden","true");
    rewardInProgress=false;
    res();
  },1400));
}

document.querySelectorAll(".task-form").forEach(form=>{
  form.addEventListener("submit",async ev=>{
    ev.preventDefault();
    const id=form.dataset.taskId;
    const btn=form.querySelector(".task");
    if(!id||btn?.dataset.busy==="1")return;
    if(btn)btn.dataset.busy="1";
    try{
      const r=await fetch(`/api/task/${id}/toggle`,{method:"POST"});
      const d=await r.json();
      if(!d.ok)throw 0;
      if(d.completed){
        btn?.classList.add("completed");
        const check=btn?.querySelector(".check");
        if(check)check.textContent="✓";
        await showReward(d.reward);
      }
      location.reload();
    }catch(_){form.submit()}
  });
});

applyLivingRoomExtras();
updateClock();
loadWeather();
checkForUpdates();

setInterval(updateClock,10000);
setInterval(checkForUpdates,1500);
setInterval(loadWeather,15*60*1000);

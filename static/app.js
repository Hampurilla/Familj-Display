let knownVersion = null;
let rewardInProgress = false;

async function checkForUpdates() {
  if (rewardInProgress) return;
  try {
    const response = await fetch("/api/version", { cache: "no-store" });
    const data = await response.json();

    if (knownVersion === null) {
      knownVersion = data.version;
      return;
    }

    if (data.version !== knownVersion) {
      const active = document.activeElement;
      const typing = active && ["INPUT", "SELECT", "TEXTAREA"].includes(active.tagName);
      if (!typing) location.reload();
    }
  } catch (_) {}
}

function updateClock() {
  const now = new Date();
  const clock = document.getElementById("clock");
  const dateEl = document.getElementById("date");

  if (clock) {
    clock.textContent = now.toLocaleTimeString("sv-SE", {
      hour: "2-digit",
      minute: "2-digit"
    });
  }
  if (dateEl) {
    dateEl.textContent = now.toLocaleDateString("sv-SE", {
      weekday: "long",
      day: "numeric",
      month: "long"
    });
  }
}

async function loadWeather() {
  const card = document.getElementById("weatherCard");
  if (!card) return;

  try {
    const response = await fetch("/api/weather", { cache: "no-store" });
    const data = await response.json();
    if (!data.ok) throw new Error("weather");

    document.getElementById("weatherIcon").textContent = data.icon;
    document.getElementById("weatherTemp").textContent = `${data.temp}°`;
    document.getElementById("weatherText").textContent =
      `${data.text} · känns ${data.feels}° · ${data.wind} km/h`;
    document.getElementById("weatherPlace").textContent = data.name;

    const forecast = document.getElementById("forecast");
    forecast.innerHTML = data.days.map(day => `
      <div class="forecast-day">
        <span>${day.label}</span>
        <strong>${day.icon} ${day.max}°</strong>
        <small>${day.min}°</small>
      </div>
    `).join("");
  } catch (_) {
    document.getElementById("weatherText").textContent = "Väder ej tillgängligt";
  }
}

function showReward(reward) {
  if (!reward) return Promise.resolve();

  rewardInProgress = true;
  const overlay = document.getElementById("rewardOverlay");
  if (!overlay) {
    rewardInProgress = false;
    return Promise.resolve();
  }

  document.getElementById("rewardEmoji").textContent = reward.emoji;
  document.getElementById("rewardMessage").textContent = reward.message;
  document.getElementById("rewardPoints").textContent = `+${reward.points} poäng`;

  overlay.classList.add("show");
  overlay.setAttribute("aria-hidden", "false");

  return new Promise(resolve => {
    setTimeout(() => {
      overlay.classList.remove("show");
      overlay.setAttribute("aria-hidden", "true");
      rewardInProgress = false;
      resolve();
    }, 1250);
  });
}

document.querySelectorAll(".task-form").forEach(form => {
  form.addEventListener("submit", async event => {
    event.preventDefault();

    const taskId = form.dataset.taskId;
    const button = form.querySelector(".task");
    if (!taskId || button.dataset.busy === "1") return;

    button.dataset.busy = "1";

    try {
      const response = await fetch(`/api/task/${taskId}/toggle`, {
        method: "POST",
        headers: { "X-Requested-With": "fetch" }
      });
      const data = await response.json();
      if (!data.ok) throw new Error("toggle");

      if (data.completed) {
        button.classList.add("completed");
        const check = button.querySelector(".check");
        if (check) check.textContent = "✅";
        await showReward(data.reward);
      }

      location.reload();
    } catch (_) {
      form.submit();
    }
  });
});

setInterval(checkForUpdates, 1500);
setInterval(updateClock, 10000);
setInterval(loadWeather, 15 * 60 * 1000);
checkForUpdates();
updateClock();
loadWeather();

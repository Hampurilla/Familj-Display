let knownVersion = null;

async function checkForUpdates() {
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

setInterval(checkForUpdates, 1500);
setInterval(updateClock, 10000);
checkForUpdates();
updateClock();

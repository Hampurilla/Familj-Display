#!/bin/bash
set -euo pipefail
# Run by the desktop session, not by a root systemd service or plain SSH.
for i in $(seq 1 300); do
  if curl --fail --silent --max-time 2 http://127.0.0.1:5000/health >/dev/null; then break; fi
  sleep 2
done
BROWSER="$(command -v chromium || command -v chromium-browser || true)"
if [ -z "$BROWSER" ]; then echo 'Chromium is not installed.' >&2; exit 1; fi
mkdir -p "$HOME/.config/familj-display/chromium"
exec "$BROWSER" --kiosk --no-first-run --no-default-browser-check \
  --disable-session-crashed-bubble \
  --user-data-dir="$HOME/.config/familj-display/chromium" \
  http://127.0.0.1:5000/

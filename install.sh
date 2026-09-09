#!/bin/bash
set -euo pipefail
# Optional installer for Raspberry Pi OS Desktop. Does not delete any app/data directory.
if [ "$(id -u)" = 0 ]; then echo 'Run as your ordinary user, not with sudo.'; exit 1; fi
ROOT="$(cd "$(dirname "$0")" && pwd)"
USER_NAME="$(id -un)"
if [[ "$ROOT" == *" "* ]]; then echo 'Use an app path without spaces.'; exit 1; fi
cd "$ROOT"
sudo apt update
sudo apt install -y python3-venv git curl fonts-noto-color-emoji
if ! command -v chromium >/dev/null && ! command -v chromium-browser >/dev/null; then
  sudo apt install -y chromium
fi
mkdir -p data/backups "$HOME/.config/autostart"
if [ ! -x venv/bin/python ]; then python3 -m venv venv; fi
venv/bin/python -m pip install -r requirements.txt
venv/bin/python app.py --check
venv/bin/python scripts/preflight.py --database "$ROOT/data/home_display.db"
# Keep copies of service/autostart settings before changing them.
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "data/backups/setup-$STAMP"
for f in home-display.service home-display-update.service; do
  if [ -f "/etc/systemd/system/$f" ]; then cp "/etc/systemd/system/$f" "data/backups/setup-$STAMP/"; fi
done
for f in home-display.desktop home-display-bootstrap.desktop; do
  if [ -f "$HOME/.config/autostart/$f" ]; then mv "$HOME/.config/autostart/$f" "data/backups/setup-$STAMP/"; fi
done
sed -e "s|/home/admin/home-display|$ROOT|g" -e "s|User=admin|User=$USER_NAME|g" home-display.service | sudo tee /etc/systemd/system/home-display.service >/dev/null
sed -e "s|/home/admin/home-display|$ROOT|g" -e "s|User=admin|User=$USER_NAME|g" deploy/home-display-update.service | sudo tee /etc/systemd/system/home-display-update.service >/dev/null
sed "s|/home/admin/home-display|$ROOT|g" home-display.desktop > "$HOME/.config/autostart/home-display.desktop"
if [ -d .git ]; then git config core.filemode false; fi
sudo systemctl daemon-reload
sudo systemctl enable home-display.service home-display-update.service
sudo systemctl restart home-display.service
printf '\nReady. Check http://YOUR-PI-IP:5000/admin\n'
printf 'Desktop auto-login must already be enabled for kiosk autostart.\n'
printf 'Old settings are in data/backups/setup-%s. No database was deleted.\n' "$STAMP"

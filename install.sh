#!/bin/bash
set -e

APP_DIR="/home/admin/home-display"

echo "Installerar Home Display..."

sudo apt update
sudo apt install -y python3-venv git chromium

mkdir -p "$APP_DIR"
mkdir -p "$APP_DIR/data"
mkdir -p /home/admin/.config/autostart

if [ ! -d "$APP_DIR/venv" ]; then
  python3 -m venv "$APP_DIR/venv"
fi

"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

sudo cp "$APP_DIR/home-display.service" /etc/systemd/system/home-display.service
cp "$APP_DIR/home-display.desktop" /home/admin/.config/autostart/home-display.desktop

chmod +x "$APP_DIR/update.sh"

sudo systemctl daemon-reload
sudo systemctl enable home-display
sudo systemctl restart home-display

echo
echo "Klart."
echo "Display: http://localhost:5000"
echo "Admin:   http://$(hostname -I | awk '{print $1}'):5000/admin"
echo
echo "Starta om Raspberry Pi när du vill testa kiosk-autostart:"
echo "sudo reboot"

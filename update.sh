#!/bin/bash
set -e

cd /home/admin/home-display

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Ingen Git-repository konfigurerad. Kör appen som den är."
  exit 0
fi

git fetch origin main

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
  echo "Redan senaste versionen."
  exit 0
fi

echo "Ny version hittad. Uppdaterar..."
git reset --hard origin/main

/home/admin/home-display/venv/bin/pip install -r requirements.txt

sudo systemctl restart home-display

echo "Uppdatering klar."

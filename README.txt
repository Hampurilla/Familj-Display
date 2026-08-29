HOME DISPLAY

Första installation:
1. Kopiera hela mappen till /home/admin/home-display
2. Kör:
   cd /home/admin/home-display
   chmod +x install.sh update.sh
   ./install.sh
3. Starta om:
   sudo reboot

Admin:
http://RASPBERRY-IP:5000/admin

Display:
http://RASPBERRY-IP:5000

GitHub senare:
- Lägg detta projekt i ett GitHub-repo.
- På Pi:n: git remote add origin <repo-url>
- git branch -M main
- git fetch origin
- Därefter kan ./update.sh hämta ny kod.
- data/ ligger utanför Git och raderas inte vid uppdatering.

Funktioner:
- Profiler
- Dagliga/veckovisa/varannan-vecka/månadsuppgifter
- Engångsuppgifter
- Svårighetsgrad 1-10
- Automatisk rättvis tilldelning
- Fast person som alternativ
- Datum och kommande uppgifter
- Förseningsmarkering
- Auto-refresh på display
- SQLite WAL för bättre stabilitet
- Chromium kiosk vid inloggning
- Systemd-service för servern

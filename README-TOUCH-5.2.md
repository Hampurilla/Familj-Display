# Familj Display – Touch 5.2

Färdiga ersättningsfiler till Familj Display v5 från den här konversationen.
Det här är en uppdatering, inte en fristående nyinstallation.
Ingen patcher behöver köras.

## Vad som ändras

Väggdisplayens startsida, uppgiftsvy och märkessamling får:

- Dolda rullningslister, både på dokumentet och inuti rullbara områden.
- Vanlig inbyggd touchscroll när Chromium rapporterar riktig touch.
- Dragscroll när pekskärmen rapporteras som mus, inklusive tomma ytor.
- Drag på länkar, profilkort och uppgiftsknappar utan HTML-drag-och-släpp.
- Skillnad mellan tryck och drag. Ett drag ska aldrig bocka av en uppgift.
- Kort efterglidning för musliknande drag, som stannar vid ny beröring.
- Ingen simulerad efterglidning om minskad rörelse är valt i webbläsaren.
- Uppdateringar från admin väntar tills pågående drag/rullning är klar.
- En touchtestsida med klickräknare och information om mottagen inmatningstyp.

Admin och inloggningen laddar INTE touchmodulen eller dess CSS. Mobilen behåller
vanlig scroll, textmarkering, tangentbord och formulär. Designen är samma som i v5.

static/style.css och static/app.js är kompletta ersättningar. De tar bort den
äldre v5.1-patchens globala CSS/JS. Behåll därför inte gamla tillägg längst
ner i de två filerna. Lägg inte tillbaka den tidigare patchen efter uppdateringen.

## Installation på Windows / GitHub

1. Packa upp ZIP-filen.
2. Kopiera ALLT INNEHÅLL till din befintliga repomapp:

   C:\Users\hampu\OneDrive\Skrivbord\Familj-Display

   Slå ihop mapparna och ersätt de gamla filerna. Lägg inte ZIP-filen eller en
   extra mappnivå i repot. Till exempel ska static/touch-kiosk.js ligga direkt
   i repots redan befintliga static-mapp. Radera inte repot, .git eller data/.

3. Kör i PowerShell:

```powershell
cd "C:\Users\hampu\OneDrive\Skrivbord\Familj-Display"
git add -- static templates/base.html README-TOUCH-5.2.md docs/touch-5.2 tests/run_touch_browser_tests.py
git commit -m "Touch 5.2 - dragscroll for display"
git push
```

4. Starta om Raspberry Pi:n med din befintliga GitHub-uppdaterare:

```bash
sudo reboot
```

Det behövs inga nya Python-paket, inga OS-ändringar och ingen ny autostart.
Behåll din separata Chromium-profil och flaggan --disable-gpu som fungerade.
Kör inte gamla install.sh eller apply_touch_scroll.py för den här uppdateringen.

## Kontrollera att den nya versionen verkligen visas

På väggdisplayen finns en ny rad längst ner:

    Touch 5.2 · testa skärmen

Det är frontend-versionen. Backendens /health kan fortfarande visa 5.0.0,
eftersom Python-backend och databasschema inte ändras av det här paketet.

Testsidan går också att öppna direkt i Chromium PÅ PI:N:

    http://127.0.0.1:5000/static/touch-test.html

Där finns avsiktligt en lång sida. Dra på tomma ytor, på det gröna
länkkortet och på knappen. Scrollvärdet ska ändras, men klickräknaren ska
inte öka av drag. Ett kort tryck ska öka den en gång. Texten "Mus / musemulerad
touch" är inte ett fel: versionen hanterar just det också.

En sida där allt redan ryms kan inte rullas. Prova därför i märkessamlingen,
en lång uppgiftslista eller testsidan. Inmatningsfält är avsiktligt inte
draghandtag; det måste fortfarande gå att skriva i dem.

Om du inte kan nå fotraden med fingret går mushjul, Page Down eller End fortfarande
att använda. Skicka vad touchtestsidan visar, inte bara en skärmbild av färgerna.

## Data och tjänster

Paketet innehåller ingen databas, inga profiler, ingen .git-katalog och ingen venv.
Det ändrar inte app.py, familj/, requirements.txt eller några systemd-/bootfiler.
Belöningar, datum, återkommande jobb, väder och skärmsläckare använder
samma backend som tidigare. Asset-versioneringen i v5 gör att de nya filerna
får en ny cache-nyckel när appen startas om.

## Testning och begränsning

Se docs/touch-5.2/TESTRESULTAT.md och touch-browser-results.json.
Testerna kör den faktiska HTML/CSS/JavaScript-koden i Chromium med musrörelser
och simulerade touchrörelser. API-svaren till testet kommer från en lokal
adapter och tillfällig testdatabas, inte din Pi eller din Flask-process.
Den fysiska Touch Display 2 har inte kunnat provas här.

Testsuiten finns i tests/run_touch_browser_tests.py. Den är till för en
testdator med Playwright, Jinja2 och Chromium, inte något som ska startas i
bakgrunden på Pi:n. Befintliga tests/render_support.py och familj/ från v5 behövs.

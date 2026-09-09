# hemma. / Familj Display 5.0

En lokal familjedisplay med varm sand, salvia, lera, honung och mörkgröna kontraster.
Byggd för Raspberry Pi 3B, Raspberry Pi OS Desktop, Python 3.13 och Touch Display 2 i liggande läge. Huvudlayouten är kontrollerad i 1280 × 720; mobiladmin i 390 × 844.

## Börja här: befintlig installation

**Radera inte appmappen, `data/` eller databasen.** ZIP-filen innehåller ingen databas, inga familjeuppgifter, ingen `.git`-mapp och inga inloggningsuppgifter.

1. Packa upp hela ZIP-innehållet över din lokala `Familj-Display`-mapp på Windows. `app.py` ska ligga direkt i repots rot, inte i en extra undermapp.
2. Kör detta i **CMD**, terminalen som visar `C:\Users\hampu>`:

```cmd
cd /d "C:\Users\hampu\OneDrive\Skrivbord\Familj-Display"
git status
git add .
git commit -m "Familj Display v5 - hemma"
git push
```

3. Starta om Raspberry Pi:n via skrivbordets omstartsmeny eller `sudo reboot`. Den tidigare konfigurerade uppdateraren ska då hämta `main` och installera `requirements.txt`. **Internet behövs vid denna uppdatering**, bland annat för den nya serverkomponenten Waitress.
4. Öppna `/admin`. Version `5.0.0` visas i inställningarna. `/health` innehåller också version och bygg-id. Skapa inte nya testprofiler förrän du kontrollerat att dina tidigare profiler finns kvar.

Appen startas fortfarande med `venv/bin/python app.py` och lyssnar på `0.0.0.0:5000`. Din befintliga app-service behöver därför normalt inte ändras för att prova version 5. Pi:ns egen webbläsare använder `http://localhost:5000`; mobilen använder `http://PI-ADRESS:5000/admin`, inte localhost.

## Vad som ingår

- Huvudskärm med klocka, datum, vecka, hälsning, horisontellt väder, familjeläge och personliga profilfärger.
- Tydlig egen uppgiftslista. Knappen **En i taget** visar en uppgift i fokus. Klart idag och kommande uppgifter ligger separat.
- Engångs-, dags-, vecko-, varannan-vecka- och månadsscheman. Start/slutdatum, beskrivning, 1–10 poäng, fast eller automatisk tilldelning.
- Aktiva personer, tillåtna personer per uppgift och arbetsandel 0,5 / 1 / 1,5 / 2 per profil.
- **144 olika märken** med svenska namn och fyra rariteter. Samling med filter, dubbletträkning och varierade belöningstexter.
- Nya märken delas ut högst en gång per uppgiftstillfälle. Att ångra och bocka av igen ger inte fler märken.
- Lokal, animerad stad som skärmsläckare, normalt efter 15 minuter. Ingen video behöver laddas ned eller strömmas.
- Valbart nattfönster, normalt 22:30–07:00, med svart webbyta efter inaktivitet. Ett tryck väcker; trycket går inte vidare till en uppgift bakom.
- Mobilanpassad admin med fyra flikar, platsökning för väder, hälsning till familjen, något att se fram emot och frivillig admin-PIN.
- Automatiska uppdateringar av skärmens innehåll. Osparade adminformulär ersätts inte vid en sådan uppdatering.
- Databassäkerhetskopia före schemaändringar och en nedladdningsknapp för backup i admin.

**Ingen TTS, högtalarkoppling, medicinhantering eller medicinsk behandlingsfunktion ingår.** Belöningarna är en valbar gränssnittsfunktion, inte en utlovad behandling.

## Data och migrering

Standardfilen är `data/home_display.db`. Om bara den äldre rotfilen `home_display.db` finns, kopieras den med SQLite:s backup-API; originalet sparas. Om båda finns används `data/home_display.db` och inget slås ihop automatiskt.

Migreringen lägger till tabeller och kolumner i en transaktion. Den behåller kända profil-, uppgifts- och schema-id:n, titlar, poäng, status, tidsstämplar och inställningar. Före migrering sparas en kontrollerad SQLite-kopia i `data/backups/`. En skadad eller nyare databas avvisas i stället för att raderas.

Migrering har testats mot scheman från de tidigare v1/v2/v3-paketen i konversationen och det tidigaste `people/person_id`-schemat. **Din riktiga Pi-databas har inte varit tillgänglig här.** Egna senare schemaändringar kan behöva granskas separat. De gamla v2/v3-paketen som undersöktes sparade inte någon permanent märkessamling. Sådan historik går inte att återskapa i efterhand. En befintlig `user_badges`-tabell med det tidigare beskrivna schemat behålls.

Att arkivera en profil eller avsluta ett schema tar inte bort historik. Nya framtida uppgifter upphör och ogjorda tillfällen avbryts eller flyttas enligt tilldelningsreglerna. Arkiverade poster är inte synliga i normalvyn; återaktivering via admin ingår inte i denna version.

## Schemaläggning och rättvisa

Systemet fördelar nya jobb efter planerade poäng under samma kalendervecka plus äldre ogjorda jobb, dividerat med profilens arbetsandel. Redan avklarade jobb inom veckan räknas fortfarande. Vid lika poäng beaktas dagen och vem som senast hade uppgiften. Detta är en begriplig utjämning, inte en garanti för exakt lika belastning. Ett stort jobb kan inte delas i bråkdelar. Manuella jobb och begränsningar respekteras.

Befintliga tilldelningar flyttas inte slumpmässigt när en ny person läggs till. Nya uppgifter fördelas med den nya personen medräknad. Vid profilarkivering flyttas ogjorda autojobb om det finns en annan tillåten person.

Tidzon: **Europe/Stockholm**. Månadsscheman den 31:a använder sista dagen i kortare månader och går tillbaka till den 31:a när den finns. Varannan vecka räknas i kalenderdagar från startdatum. Normalt genereras idag plus 14 dagar. Efter avbrott fylls högst 31 missade dagar på. Detta undviker att en långt avstängd skärm plötsligt skapar flera års sysslor.

## Nattläge, skärm och prestanda

Svart nattläge är **svart bild, inte fysisk avstängning av LCD-bakgrundsbelysningen**. Paketet ändrar inga GPIO- eller backlight-behörigheter. Animationen är inte en garanti mot bildretention eller slitage.

Skärmsläckaren har högst 20 ritningar per sekund, färre vid begärd reducerad rörelse, och pausas i nattläge och dolda flikar. Den körs inte i mobiladmin. Klockan i scenen rör sig också. Nattfönstret och nya inställningar utvärderas även när scenen redan visas.

Ingen React/Vue, inga CDN-resurser och inga levererade fontfiler. Vanliga systemfonter och installerad Noto Color Emoji används. Statisk kod får versionshash i URL:erna. Data-API och HTML får `no-store`.

## Väder och integritet

Väder och ortsökning använder Open-Meteo. Koordinater respektive söktext skickas till den tjänsten. Profiler, uppgifter och märken skickas inte dit. Prognosen hämtas separat i bakgrunden och sparas lokalt. Vid nätfel visas en tydligt markerad sparad prognos eller ett lugnt felmeddelande; uppgifter fortsätter fungera. De nya Python-paketen behöver först installeras online innan appen kan användas helt offline.

Admin-PIN är valfri och lagras hashad. CSRF-skydd, inputvalidering och automatisk HTML-escaping ingår. PIN är inte en ersättning för krypterad transport: appen använder lokal HTTP. **Öppna inte port 5000 mot internet.** Använd ett betrott hemnät, inte ett publikt Wi-Fi. Displayens avbockning kräver inte PIN, avsiktligt.

## Bättre uppdaterare och kioskstart: frivillig engångsinstallation

Din gamla uppdaterare under `/usr/local/bin` ändras inte av att en ZIP läggs på GitHub. Den fortsätter fungera enligt sin gamla logik.

För att installera den nya, stegvis kontrollerande uppdateraren och kioskstarten, kör **en gång på Pi:n**, efter att v5-filerna har hämtats:

```bash
cd ~/home-display
bash install.sh
```

Kör som `admin`, inte `sudo bash install.sh`. Scriptet begär själv sudo när det behövs. Det säkerhetskopierar gamla service-/autostartfiler, installerar beroenden, testar kandidatappen med tom databas och databaskopia, och installerar systemd-filerna. Befintlig Desktop auto-login måste vara aktiverad för kiosk vid start; installationsscriptet ändrar inte inloggningsinställningar.

Den nya uppdateraren testar ny kod och Python-miljö separat innan bytet. Den vägrar skriva över lokala versionsstyrda ändringar, avbruten Git-historik eller databasfiler som råkat bli incheckade. Utan kontakt med GitHub används lokal installation. Vid misslyckad manuell start återställs kod och miljö; databasen skrivs **inte** tillbaka automatiskt eftersom nya avbockningar annars kan gå förlorade. En backup sparas. Detta eliminerar inte alla felrisker vid strömbortfall eller framtida databasmigreringar.

Manuell uppdatering med den nya uppdateraren:

```bash
cd ~/home-display
sudo -v
bash update.sh
```

Den är avsedd för det normala Pi-kontot med rätt att starta/stoppa `home-display.service`. Varje ny version kan spara en separat Python-miljö under `data/environments/`. Gamla miljöer städas inte automatiskt; kontrollera diskutrymme efter många uppdateringar.

## Kontroll och felsökning

```bash
cd ~/home-display
./venv/bin/python app.py --check
./venv/bin/python scripts/preflight.py --database data/home_display.db
./venv/bin/python -m unittest discover -s tests -v
curl http://localhost:5000/health
systemctl status home-display --no-pager
journalctl -u home-display -n 60 --no-pager
```

`--check` testar en tom tillfällig databas. `preflight.py` arbetar på **en kopia** och ändrar inte den riktiga databasen. Båda kräver installerat Flask. Fullständig redovisning av vad som faktiskt körts i byggmiljön finns i [docs/TESTS.md](docs/TESTS.md).

Efter ett byte från en mycket gammal frontend kan en första vanlig omladdning av webbläsaren behövas. Därefter gör v5:s versionskontroll detta när appkoden byts, utan att kasta bort adminutkast. Synkmarkeringen visar kontakt med Pi:n, inte tillgängligt internet.

## Struktur

```text
app.py                  Flask-routes och Waitress-start
familj/store.py          transaktioner, migrering, scheman, tilldelning, märken
familj/weather.py        bakgrundshämtning och vädercache
familj/badges.py         stabil katalog med 144 märken
templates/              hela vägggränssnittet och mobiladmin
static/                 CSS, JavaScript och egna SVG-ikoner
scripts/                förkontroll, uppdaterare och kioskstart
tests/                  tester och historiska schema-fixtures
data/                   skapas lokalt, får inte läggas på GitHub
```

## Tekniska källor

- [Flask: Waitress-deployment](https://flask.palletsprojects.com/en/stable/deploying/waitress/)
- [Open-Meteo Forecast API](https://open-meteo.com/en/docs) och [Geocoding API](https://open-meteo.com/en/docs/geocoding-api)
- [Open-Meteos användarvillkor](https://open-meteo.com/en/terms)
- [Python: SQLite backup](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup)

Paketet är skapat utifrån de tidigare projektfilerna i chatten. Inga ändringar har pushats till ditt GitHub-konto eller gjorts på din Pi av detta paketleveranstillfälle.

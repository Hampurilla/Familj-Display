# Testprotokoll Home & Voice 5.4

Testat lokalt 2026-09-12, Python 3.13 och Chromium 144.0.7559.96.
Bas: det faktiska Familj-Display-v5.zip + Touch-5.2.zip, plus Remote5.3-filer från chatten.
Ingen levande Raspberry-databas eller verkligt Tailscale-konto var tillgängligt.

## Python

* 35 nya kärntester godkända.
* Hela tillgängliga testsamlingen: 101 fall, varav 83 godkända och 18 SKIP.
* De 18 SKIP är 9 tidigare och 9 nya Flask-integrationsfall. Flask saknades i
  utvecklingsmiljön. Installationsförsök mot paketindex misslyckades med nätverks/DNS-problem.
  Dessa fall har INTE verifierats här; de medföljer för Pi:ns venv.
* Kontroller: bestående profilinställningar, backup, idempotent utökning, bevarade
  uppgifter, felaktig profil, avstängd röst, argument/volymkontroll, ingen extra
  belöning, riktig svensk WAV, cache, timeout, kommandon utan shell.
* Faktisk syntes här använde installerade eSpeak (äldre), inte eSpeak NG.
  Koden föredrar eSpeak NG som guiden installerar på Pi:n.

## Webbläsare

* 26 nya kontroller godkända med Jinja + verklig Store/TTS och lokal fetch-testadapter.
* Riktig WAV genererades och dekodades/spelades av WebAudio i headless Chromium.
  Detta bevisar INTE fysiskt AUX-ljud.
* Läsknappar, stopp, separata profiler, utebliven felaktig avbockning,
  belöningsuppläsning med rätt jobb-ID, uppdaterat innehåll, adminformulär,
  manifest och mobiladress testades i 390 px och 1280 px.
* Alla 37 befintliga touchkontroller godkända i DELADE körningar:
  34 godkända före testmiljöns timeout; resterande 3 i separat körning.
  Två försök till full körning avslutades av timeout efter samma 34 tester.
* Mobiladresser i testbilder är uttryckliga testdata, inte användarens riktiga adress.

## Bevarandekontroll

17 kärn-/touch-/startfiler jämfördes byte för byte och är oförändrade i testinstallationen.
Se PRESERVATION.json. Bara registrering/nya länkar/resurser läggs i app.py, admin.html och base.html.
ZIP-paketet innehåller inte ersättningsfiler för de tre; apply-verktyget integrerar försiktigt.

## Återstår på verklig hårdvara

* ./venv/bin/python app.py --check och test_homevoice54*.py med riktig Flask.
* AUX-utgång, volym, begriplighet och svarstid på just Pi 3B.
* Safari/iOS hemskärmsikon och VPN On Demand.
* Tailscale-login, faktisk domän/Serve/TLS/policy och kontakt på Wi-Fi respektive 4G/5G.

Kör kärntester med:

    ./venv/bin/python -m unittest discover -s tests -p 'test_homevoice54*.py'

Webbläsartestet kräver Playwright och lokal Chromium på en testdator:

    python tests/run_homevoice54_browser.py

Testerna använder tillfälliga databaser och ändrar inte familjens riktiga data.

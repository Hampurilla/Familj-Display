# Familj Display Home & Voice 5.4

Tillägg för befintliga Familj Display v5, Touch 5.2 och valfri Remote 5.3.
Det är INTE en separat app att installera i stället för hela projektet.
Kopiera in innehållet i befintligt repo, kör förberedelsen och pusha.

## Vad det gör

* Samma Tailscale HTTPS-adress för mobilikonen på både hemma-Wi-Fi och 4G/5G.
* /admin/mobile visar den verkliga adressen och en engångsguide för iPhone.
* Manifest med samma relativa startadress /admin. Ingen omskrivning till lokala IP-adresser.
* /admin/speech har separat ljudinställning per profil. Alla är tysta som standard.
* Läs mina uppgifter, Läs vid varje jobb, Stoppa, valbara instruktioner och belöningsröst.
* Lokalt svenskt eSpeak NG, tempo och volym per profil, begränsad ljudcache.
* Ljud spelas i enheten där man trycker. På väggdisplayen: Pi:ns ljudutgång.
  På telefonen: telefonens ljudutgång. Inga fjärrkommandon spelar oväntat upp ljud hemma.

Det här är en liten syntetisk/robotlik röst, inte Piper eller en naturlig neural röst.
Det krävs ingen stor röstmodell. Ingen moln-TTS används. Efter installation fungerar
uppläsningen lokalt utan internet. eSpeak (äldre) kan användas som reserv om det redan finns.

## 1. Kopiera på Windows

Packa upp innehållet i ZIP-filen över:

    C:\Users\hampu\OneDrive\Skrivbord\Familj-Display

Slå ihop mapparna. RADERA INTE projektmappen, .git, data/ eller databasen.
Paketet innehåller nya tilläggsfiler samt samma Remote 5.3-filer som tidigare.
Det behövs inte att Remote 5.3 redan är installerat.

I POWERSHELL (inte CMD):

```powershell
cd "C:\Users\hampu\OneDrive\Skrivbord\Familj-Display"
py scripts/apply_home_voice.py --check
py scripts/apply_home_voice.py
```

Stanna om något säger STOP. Verktyget ska känna igen din befintliga v5-struktur.
Det lägger registrering i app.py, adminlänkar i templates/admin.html och tilläggsresurser i
templates/base.html. Originalkopior sparas utanför Git under ~/.familj-code-backups/.
Att köra verktyget igen skapar inte dubbla krokar. Befintlig touch och skärmsläckare behålls.

```powershell
git add -- app.py familj templates static scripts docs/homevoice-5.4
git add -- tests/test_homevoice54.py tests/test_homevoice54_flask.py tests/run_homevoice54_browser.py README-HOMEVOICE-5.4.md
git diff --cached --stat
git commit -m "HomeVoice 5.4 - same mobile address and local speech"
git push
```

Granska git diff --cached --stat och lägg inte till data/, lösenord eller nycklar.
Kommandona ovan lägger avsiktligt INTE till hela projektmappen med git add .

## 2. Hämta på Raspberryn

Din gamla updater kan hämta ändringen vid omstart. Manuellt i SSH:

```bash
cd ~/home-display &&
git pull --ff-only &&
./venv/bin/python app.py --check &&
sudo systemctl restart home-display
```

Om git rapporterar konflikt: stanna, spara/granska dina lokala ändringar.
Använd inte git reset --hard som snabb lösning. Kör inte app.py parallellt med
tjänsten på samma port. Inga nya Python-beroenden behövs och kör INTE gamla install.sh.
Kioskprofil, --disable-gpu, progressbar och GitHub-updater lämnas som de är.

Kontrollera:

```bash
curl --fail http://127.0.0.1:5000/health
```

Svaret innehåller homevoice_version: 5.4.0. Huvudappens versionsnummer är oförändrat.
Efter omstart/laddning av ny version visas två nya länkar i admin.

## 3. Installera lokal svensk uppläsning en gång

Som användaren admin på Pi:n, utan sudo framför python:

```bash
cd ~/home-display
python3 scripts/setup_home_voice.py voice
```

Du får godkänna installation av paketet espeak-ng via dina befintliga OS-repon.
Guiden begär sudo bara för apt-get. Den provgenererar en svensk WAV i en tillfällig
mapp, men spelar inte själv upp den. Ingen ändring görs i ljudutgång eller systemvolym.

På Pi:ns skrivbord: öppna ljudmenyn och välj Headphones / Analog Stereo / 3,5 mm.
Kontrollera volym och att ljudet inte är avstängt. Detta är normalt en engångsinställning.
Det kan även kontrolleras i terminalen med wpctl status; välj rätt sink-ID med
wpctl set-default ID. Gissa inte sink-ID: olika maskiner har olika nummer.

Pi:ns 3,5 mm-utgång är inte en effektförstärkare för lösa högtalare.
En aktiv högtalare/förstärkare kan behövas för tillräcklig volym.
Ingen GPIO-anslutning behövs för denna version.

I admin -> Uppläsning per profil:
1. Aktivera exempelvis lillebrors profil.
2. Välj tempo, volym, instruktioner och eventuell belöningsröst.
3. Spara. Prova på väggdisplayen genom att trycka Läs.

Nya inställningar visas utan reboot (upp till 12 sekunder). En första knapptryckning
behövs för att webbläsaren ska tillåta ljud. Det finns ingen automatisk uppläsning
bara för att en profil öppnas. Belöningsrösten kan starta efter en aktiv avbockning.
Stoppa avbryter uppspelning/kö; redan påbörjad servergenerering kan slutföras till cachen.
Byter man flik/sida eller vilar skärmen stoppas ljudet.

## 4. Samma mobiladress hemma och borta

Sätt en admin-PIN med 6-12 siffror under befintliga Inställningar.
Kör på Pi:n:

```bash
python3 scripts/setup_home_voice.py remote
python3 scripts/setup_home_voice.py address
```

Följ Tailscales inloggning/godkännande. Den befintliga Remote-guiden kontrollerar
konflikter och konfigurerar bara privat Serve. Den gör INTE appen offentlig med Funnel,
öppnar inte routerportar och ändrar inte SSH/kiosk. Befintlig korrekt konfiguration behålls.

ADDRESS-kommandot skriver ut den VERKLIGA adressen. Den har formen:

    https://<pi-namn>.<tailnet-namn>.ts.net/admin

Ovanstående är en formbeskrivning, inte din riktiga länk. Ingen äkta adress kan
härledas från din gamla lokala IP. Verktyget skriver inte ut en gissning.
Adressen visas också under /admin/mobile. Använd inte 192.168.x.x för mobilikonen.

På mammans iPhone:
1. Installera Tailscale och anslut till ert Tailscale-nätverk. Bjud in hennes egna konto.
2. Settings -> VPN On Demand -> Wi-Fi: Always och Cellular: Always.
   Undanta INTE hemmets Wi-Fi. Andra VPN-appar kan konkurrera.
3. Öppna den riktiga HTTPS-adressen i Safari. Logga in med admin-PIN.
4. Dela -> Lägg till på hemskärmen -> Öppna som webbapp (om visat).
5. Prova nya ikonen på Wi-Fi, sedan med Wi-Fi av och mobildata på.
6. Ta bort den GAMLA lokala appikonen när båda testerna fungerar.

Hon behöver inte kopiera/byta länk efter den engångsinställningen.
Tailscale måste vara anslutet på båda näten. Vid reautentisering/utgången nyckel kan
inloggning behöva förnyas. Pi:n ska vara på och ha internet för åtkomst utifrån.
Hemma använder väggdisplayen fortfarande localhost och fungerar utan internet.
Om ni byter Tailscale-nätverk/enhetsnamn kan adressen ändras.
Domännamnet i HTTPS-certifikatet registreras offentligt, men innehållet är privat.

## Data, säkerhet och bevarande

* Inga befintliga tabeller raderas eller skrivs om av detta tillägg.
* En separat tabell fd_voice_profiles läggs till i samma SQLite-databas.
* SQLite-backup tas före tilläggstabellen skapas. Sparas i data/backups/.
* Ljudcachen ligger i data/voice-cache, ingår inte i Git och begränsas till 120 WAV/32 MiB.
* Endpointen läser bara befintliga uppgifter/belöningar för rätt aktiva profil.
  Den tar inte emot valfri text eller shellkommandon från klienten.
* CSRF-skyddet behålls. Ljudinställningar skyddas av befintlig admin-PIN.
  Själva familjeprofilerna har samma lokala åtkomstmodell som tidigare.
* Läsknappar ger inte nya poäng eller märken.
* CSS/JS för touch, skärmsläckare och befintlig app byts inte ut.
* Ingen service worker cachear privata uppgifter eller en annan serveradress.
* Tillägget ger inte assistenten åtkomst till Tailscale eller Raspberryn.

## Kontroll och felsökning

```bash
./venv/bin/python -m unittest discover -s tests -p 'test_homevoice54*.py'
python3 scripts/setup_home_voice.py address
systemctl status home-display --no-pager
journalctl -u home-display -n 50 --no-pager
```

Läsknappar saknas: aktivera och SPARA just den profilen, vänta 12 sekunder eller ladda om.
Ingen röst installerad: kör voice-kommandot på Pi:n, inte Windows. Vänta cirka 20 sekunder
på att motorns statuscache förnyas. Kontrollera svenska med espeak-ng --voices=sv.
Ljudet hörs i mobilen: detta är avsiktligt. Testa på väggdisplayen för AUX.
Borta fungerar inte: kontrollera Tailscale på BÅDA enheterna, konto/inbjudan, Serve,
PIN, internet, nyckelutgång och eventuell annan VPN. Den gröna statusen bekräftar
konfiguration, inte att varje mobilnätverk kan nå Pi:n.

Skicka aldrig PIN, lösenord, tokens, inloggningslänkar eller fullständig peer-status.

## Testomfattning

Se docs/homevoice-5.4/TESTRESULTAT.md. Det finns inga löften om fysisk testning som inte utförts.
Flask-integrationsfallen behöver köras i Pi:ns befintliga venv. Inget har pushats eller
aktiverats på dina enheter av paketleveransen.

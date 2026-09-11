# Touch 5.2 – testresultat

## Sammanfattning

**37 webbläsartester godkända, 0 underkända.**

Chromium 144.0.7559.96, headless på Linux x86_64, startat med --disable-gpu.
Den faktiska appens mallar renderades med Jinja. Faktisk CSS och JavaScript
kördes i webbläsaren. Musrörelser skickades med Playwright och native-touch
simulerades via Chromiums Input.dispatchTouchEvent. Datorns Chromium fick
ingen säkerhetspolicy ändrad; HTML och resurser laddades direkt från lokala filer
i testet, utan extern navigering.

API-svaren kom från en lokal testadapter med projektets riktiga Store och en
tillfällig testdatabas. Vädret var exempeldata. Detta är inte ett test mot
användarens Raspberry Pi, dess databas eller en körande Flask-server.

## Testade beteenden

- Inga rullningslister på startsida, profil eller märkessamling.
- Musliknande fingerdrag på tomma ytor i samtliga tre vyer.
- Simulerad riktig touch i samtliga tre vyer.
- Drag på profilkort flyttar sidan utan att öppna länken.
- Drag på avbockningsknappen flyttar sidan utan att skicka avbockning.
- Vanliga tryck fungerar, både med musinmatning och native touch.
- Ett litet fingerjitter blir inte automatiskt ett drag.
- Nästa avsiktliga tryck fungerar direkt efter ett drag.
- Nedåtdrag, sidans slut och omvänd riktning fungerar.
- Mushjul och tangentbord fungerar fortfarande.
- Efterglidning upphör vid ny beröring och stängs av med reduced motion.
- Inre rullbara områden och fortsättning till förälderns rullning.
- Nya profilkort som infogas med liveuppdatering kan också dras.
- Liveuppdatering inväntar ett pågående drag, även för native touch som hålls stilla efter rullning.
- Skärmsläckarens väckning aktiverar inte en dold knapp bakom den.
- Mobiladmin och inloggning laddar inte touchmodulen eller dess CSS.
- Mobiladmin behåller native scroll, textmarkering och formulärinmatning.
- Diagnostiksidan skiljer mellan drag och tryck.
- Vanliga tryck skickar en avbockning och visar belöningen.
- 1280×720 och 800×480 kontrollerades.

Detaljer för varje kontroll finns i touch-browser-results.json och browser-run.txt.

## Python och oförändrade filer

Befintlig Python-testsuite: **48 tester godkända, 9 hoppades över**.
De 9 som hoppades över är Flask-tester: Flask var inte installerat i denna
körmiljö och paketservern kunde inte nås. De ska inte räknas som godkända.
Resultatet finns i python-tests.txt. JavaScript-syntax kontrollerades med node --check.

15 backend-/admin-/servicefiler jämfördes byte för byte med v5-originalet och
var oförändrade i arbetskopian. Uppdateringspaketet innehåller inga ändringar
till dessa. De tidigare globala v5.1-tilläggen finns inte i ersättningsfilerna.

## Kvar att prova på den riktiga enheten

Den fysiska Raspberry Pi 3B, displayens drivrutin, faktiskt svarstempo och
fingerkänsla har inte kunnat provas här. Därför ges ingen 100-procentsgaranti.
Använd den inbyggda touchtestsidan för det sista provet på enheten.

## Teknisk bakgrund

MDN skiljer på pointerType mouse, touch och pen. Den nya koden låter
webbläsaren hantera native touch och lägger till separat dragscroll för
musliknande inmatning, istället för att konkurrera med native scroll.

- https://developer.mozilla.org/en-US/docs/Web/API/PointerEvent/pointerType
- https://developer.mozilla.org/en-US/docs/Web/API/Pointer_events
- https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/touch-action

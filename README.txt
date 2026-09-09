FAMILJ DISPLAY - TOUCH SCROLL v5.1
==================================

Syfte
-----
Den här patchen gör Familj Display mer touch-native:

- scrollbar syns inte
- vertikal scroll sker genom att dra fingret var som helst på innehållet
- text markeras inte av misstag på displayen
- inputs och adminformulär fungerar fortfarande normalt
- tappar fungerar fortfarande
- drag på en knapp ska inte råka aktivera knappen när avsikten var att scrolla
- konservativ JS-fallback används om Chromium inte flyttar sidan nativt

VIKTIGT
-------
Ingen kan ärligt lova 100% beteende på all hårdvara/webbläsarversioner.
Patchen innehåller både korrekt native CSS och en fallback, vilket är
så robust som det går att göra utan att ersätta Chromium.

INSTALLERA I GITHUB-REPOT PÅ WINDOWS
------------------------------------
1. Packa upp ZIP-filen.
2. Kopiera hela mappen Familj-Display-TouchScroll-v5.1 till valfri plats.
3. Öppna CMD i din Familj-Display-repo och kör patchern med Python:

   py "SÖKVÄG\Familj-Display-TouchScroll-v5.1\apply_touch_scroll.py" "C:\Users\hampu\OneDrive\Skrivbord\Familj-Display"

4. Verifiera:

   py "SÖKVÄG\Familj-Display-TouchScroll-v5.1\verify_touch_scroll.py" "C:\Users\hampu\OneDrive\Skrivbord\Familj-Display"

5. Push:

   cd /d "C:\Users\hampu\OneDrive\Skrivbord\Familj-Display"
   git add .
   git commit -m "Touch scroll v5.1"
   git push

INSTALLERA DIREKT PÅ RASPBERRY PI
---------------------------------
Packa upp mappen och kör:

   python3 apply_touch_scroll.py /home/admin/home-display
   python3 verify_touch_scroll.py /home/admin/home-display
   sudo systemctl restart home-display

Om Chromium fortfarande visar gamla CSS/JS:

   sudo reboot

TESTA PÅ TOUCH DISPLAY 2
------------------------
Testa följande:

1. Dra upp/ner mitt på bakgrunden.
2. Dra på ett profilkort utan att släppa direkt.
3. Dra på en uppgiftsrad.
4. Tryck snabbt på samma profilkort - det ska fortfarande öppnas.
5. Admin: dra sidan mellan formulärfälten.
6. Admin: tryck i ett textfält och skriv - markering/cursor ska fungera.
7. Ingen scrollbar ska synas till höger.

DIAGNOSTIK
----------
I Chromium DevTools Console kan man köra:

   familjTouchScrollDiagnostics()

Den visar bland annat scrollHeight, maxScrollY, touchAction och overflowY.

# Familj Display v2

Nyheter:
- Direkt belöning efter avbockad uppgift: slumpad djur-emoji + poäng.
- Horisontellt väderkort med 3-dagars prognos.
- Väderplats kan ändras från admin utan kod.
- Familjens dagliga progress på startsidan.
- Profilsidan fokuserar på idag; kommande uppgifter är hopfällbara.
- Stabilare SQLite-migrering så befintliga data kan behållas.
- Touchvänlig layout utan oavsiktlig textmarkering.
- Automatisk rättvis tilldelning baserad på dagens belastningspoäng.

Väder:
Open-Meteo används utan API-nyckel. Standard är Borås.
Ändra namn/latitud/longitud under Admin -> Motivation & väder.

Uppdatering:
Pi:ns systemd-updater hämtar nya commits från GitHub vid nästa omstart.
Databasen ligger i data/ och ignoreras av Git.

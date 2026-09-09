# Testprotokoll — Familj Display 5.0.0

## Vad som faktiskt har körts

Byggmiljö: Linux x86_64, Python 3.13.5, SQLite, Jinja2 och headless Chromium. Ingen Raspberry Pi var ansluten.

**57 Python-testfall: 48 godkända, 9 överhoppade.**

Godkända tester täcker scheman, dubbleringsskydd, månadsslut/skottår, varannan vecka över tidsomställning, validering, slutdatum, arbetsandelar, valda personer, avklarad arbetsbelastning, 12 samtidiga avbockningar, en belöning per uppgift, ångra, arkivering, historik, datumväxling, inställningar, hashad PIN, backup och migrering.

Migreringstesterna använder SQL-scheman extraherade från de tidigare levererade v1/v2/v3-arkiven, samt det tidigaste `people/person_id`-schemat. Befintlig collection-tabell och en avsiktligt nyare schema-version provas också. Testdata är tillfälliga, inte familjens riktiga databas.

Jinja-mallar har renderats med `StrictUndefined` för huvudskärm, person, samling, mobiladmins fyra flikar, redigering, tomt läge och escapad text. Vädertester använder kontrollerade API-svar och nätfel; de kontrollerar bland annat att sparad prognos finns kvar efter omstart och märks som gammal efter ett fel.

**29 kontroller i Chromium** genomfördes mot verklig CSS/JavaScript och renderade mallar, med Store/Jinja och en lokal testadapter i stället för Flask. Kontrollistan finns i `ui-checks.json`.

Dessa inkluderar 1280×720 utan huvudskärmsskroll, mobil390×844 utan horisontellt överflöd, synk utan dokumentomladdning, belöning efter avbockning, samlingsfilter, adminutkast som bevaras, skärmsläckare, nattväxling under pågående skärmvila, en-trycks-väckning utan klick igenom och att en simulerad skrollgest inte bockar av ett jobb. Timeoutprov använde simulerad 16-minuters inaktivitet, inte ett 16 minuter långt prestandatest.

Python-syntax, JavaScript-syntax och Bash-syntax är också kontrollerade.

## Vad som INTE har verifierats här

Flask och Waitress saknades i byggmiljön och paketservern kunde inte nås vid installationsförsöket. Därför har **de nio riktiga Flask-testklienttesterna inte körts**. De medföljer i `tests/test_flask.py` och överhoppas uttryckligen om Flask saknas. Browseradaptern ersätter inte ett test av Flask/Waitress, cookies, middleware eller vanlig resursladdning med CSP. Browsermiljön tillät inte normal sidnavigering till den lokala testservern; mallar och kod laddades därför in i renderaren och testanrop bryggades till adaptern.

Inte heller faktiskt GitHub-push, Pi-start, systemd-installation, en riktig uppdatering/rollback, fysisk touchpanel, dygnslång drift, fysisk backlight eller CPU/GPU-prestanda på Pi 3B har testats. Skärmbilderna visar **exempeldata och exempelväder**, inte livevädret i Borås.

## Säker kontroll med riktig Flask på Pi:n

Efter installation av `requirements.txt`:

```bash
cd ~/home-display
./venv/bin/python -m unittest discover -s tests -v
./venv/bin/python app.py --check
./venv/bin/python scripts/preflight.py --database data/home_display.db
```

Testerna och `--check` använder tillfälliga databaser. `preflight.py` testar mot en SQLite-kopia av den angivna databasen. Originalet ändras inte. Vid fel: behåll datafiler och loggar, radera inte databasen.

Ett frivilligt GitHub Actions-exempel finns i `github-actions.example.yml`. Det läggs inte automatiskt i `.github/workflows/`, för att en vanlig koduppladdning inte ska behöva utökade workflow-behörigheter.

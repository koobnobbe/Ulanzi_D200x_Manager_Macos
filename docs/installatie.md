# Installeren en starten

## Wat je nodig hebt

- Een Mac met macOS.
- Python 3 (getest met 3.11).
- Een Ulanzi D200X, met USB aangesloten.

## Installeren

Open een terminal in de projectmap en maak een virtuele omgeving met de benodigde pakketten:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Tijdzone van de klok

De klok op het deck gebruikt de tijdzone uit het bestand `.env` in de projectmap. Zonder dat bestand staat de klok op New Yorkse tijd. Zet er daarom deze regel in:

```
TIMEZONE=Europe/Amsterdam
```

## Starten

Start de manager vanuit de projectmap:

```
python3 d200x_manager.py
```

Wil je een ander configuratiebestand gebruiken dan `config.yaml`, geef het dan mee: `python3 d200x_manager.py ander.yaml`.

Als alles goed gaat, zie je in de terminal onder andere:

```
web interface: http://127.0.0.1:8765
active app: Code (profile: default)
Druk op een knop (Ctrl+C om te stoppen)
```

Stoppen doe je met **Ctrl+C**.

> Start de manager altijd vanuit de projectmap. Paden zoals `icons/…` en `backgrounds/…` in de configuratie zijn ten opzichte van die map.

## Toestemming voor toetscombinaties

Om toetscombinaties zoals `cmd+c` naar andere apps te sturen, heeft macOS toestemming nodig. Geef de app waarin de manager draait (Terminal, iTerm of VS Code) toegang via **Systeeminstellingen → Privacy en beveiliging → Toegankelijkheid**.

Zonder die toestemming worden gewone toetscombinaties stil genegeerd. Mediatoetsen (volume, afspelen, helderheid) werken wel. De manager waarschuwt in de terminal als de toestemming ontbreekt.

## Ulanzi Studio

Sluit Ulanzi Studio af voordat je de manager start. Beide programma's willen het deck aansturen en kunnen elkaar in de weg zitten.

## Na een update

- Wijzigingen in `config.yaml` en de profielen worden vanzelf opnieuw ingelezen.
- Na een update van de code (`.py`-bestanden) moet je de manager herstarten.
- Na een update van de webinterface ververs je de pagina met **Cmd+Shift+R**.

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

## Als app in Programma's

`tools/macos-app/build.sh --install` bouwt **D200X Manager.app** en zet die in `/Applications`. Daarvoor zijn de command line tools van Xcode nodig (`xcode-select --install`).

De app staat als icoon in de menubalk, niet in het Dock. Hij start de manager met de code en de `.venv` uit deze projectmap; wijzigingen in de code of in `config.yaml` werken dus gewoon. Het menu:

- **Webinterface openen** (ook als je de app nog een keer opent);
- **Manager herstarten**, **Log tonen** (`~/Library/Logs/D200X Manager.log`) en **Projectmap tonen**;
- **Starten bij inloggen**;
- **D200X Manager stoppen**.

Stopt de manager, bijvoorbeeld omdat het deck niet is aangesloten, dan start de app hem na 10 seconden opnieuw.

Toetsen die sneltoetsen sturen hebben **Toegankelijkheid** nodig: geef die aan **D200X Manager** in Systeeminstellingen → Privacy en beveiliging. Na een nieuwe build vraagt macOS daar soms opnieuw om. Start de manager niet tegelijk ook in de terminal: dan willen ze allebei het deck gebruiken.

Verplaats je de projectmap, bouw de app dan opnieuw.

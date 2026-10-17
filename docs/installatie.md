# Installeren en starten

## Wat je nodig hebt

- Een Mac met macOS, of een pc met Windows 11 (zie [Windows](windows.md)).
- Een Ulanzi D200X, met USB aangesloten.

## De app

D200X Manager is één programma: **D200X Manager.app** op de Mac, **D200X Manager.exe** op Windows. Python en de code zitten erin; je hoeft niets anders te installeren. Start de app en er verschijnt een icoon in de menubalk (Mac) of het systeemvak (Windows). Het menu:

- **Webinterface openen**;
- **Manager herstarten**, **Log tonen** en **Projectmap tonen** (de config-map);
- **Starten bij inloggen**;
- **D200X Manager stoppen**.

Stopt de manager, bijvoorbeeld omdat het deck niet is aangesloten, dan start de app hem na 10 seconden opnieuw. Het log staat in `~/Library/Logs/D200X Manager.log` (Mac) of `%LOCALAPPDATA%\D200X Manager\manager.log` (Windows).

## De config-map

Alles wat van jou is staat in de **config-map**:

| | |
|---|---|
| `config.yaml` | de toetsen, pagina's, draaiknoppen en instellingen |
| `profiles/` | de profielen |
| `library/` | de bibliotheken |
| `plugins/` | de plugins; hun instellingen en tokens staan in `plugins.local.yaml` |
| `icons/`, `backgrounds/` | iconen en achtergronden |
| `lang/`, `docs/` | de teksten van de app en deze documentatie |
| `.env` | de tijdzone van de klok (zie hieronder) |

Standaard is de config-map **de map waar de app (of exe) in staat**. Zet de app daarom in een eigen map, bijvoorbeeld `/Applications/D200X Manager/` of `C:\D200X Manager\`. Is die map nog leeg, dan krijgt hij bij de eerste start een startconfig met de meegeleverde bibliotheken, plugins, talen en docs.

Een andere config-map, bijvoorbeeld een git-map die je met een andere computer deelt, stel je in bij **Apparaat → Config-map**. Dat pad komt in het bestand `D200X Manager config.txt` naast de app; verwijder dat bestand om weer de map van de app te gebruiken. De manager herstart met de nieuwe map.

Bij een nieuwe versie van de app worden `docs/`, `lang/` en de meegeleverde plugins bijgewerkt. Je `config.yaml`, profielen, bibliotheken, iconen en instellingen blijven altijd zoals ze zijn.

## Tijdzone van de klok

De klok op het deck gebruikt de tijdzone uit het bestand `.env` in de config-map. Zonder dat bestand staat de klok op New Yorkse tijd. Zet er daarom deze regel in:

```
TIMEZONE=Europe/Amsterdam
```

## De app bouwen

De app bouw je uit deze projectmap, op het systeem waarvoor hij is:

- **Mac:** `tools/build-mac.sh` maakt `dist/D200X Manager.app`; met `--install` zet hij hem ook in `/Applications/D200X Manager/`.
- **Windows:** zie [Windows](windows.md).

Nodig: Python 3.11 of nieuwer en een `.venv` in de projectmap (`python3 -m venv .venv`); het bouwscript installeert de rest.

## Starten vanuit de broncode

Voor ontwikkelen kan het ook zonder app, vanuit de projectmap (na `pip install -r requirements.txt` in de `.venv`):

```
python3 main.py              # het icoon in de menubalk, dat de manager start
python3 d200x_manager.py     # alleen de manager, in de terminal (stoppen met Ctrl+C)
```

Vanuit de broncode is de projectmap de config-map, tenzij `D200X Manager config.txt` in de projectmap naar een andere wijst.

## Toestemming voor toetscombinaties (Mac)

Om toetscombinaties zoals `cmd+c` naar andere apps te sturen, heeft macOS toestemming nodig. Geef **D200X Manager** (of de terminal waarin je de manager start) toegang via **Systeeminstellingen → Privacy en beveiliging → Toegankelijkheid**. Na een nieuwe build vraagt macOS daar soms opnieuw om.

Zonder die toestemming worden gewone toetscombinaties stil genegeerd. Mediatoetsen (volume, afspelen, helderheid) werken wel.

Gebruik je een virusscanner met app-controle, zoals F-Secure, sta D200X Manager daar dan toe; anders wordt de manager direct gestopt (in het log: `exit -9`).

## Ulanzi Studio

Sluit Ulanzi Studio af voordat je de manager start. Beide programma's willen het deck aansturen en kunnen elkaar in de weg zitten.

## Na een update

- Wijzigingen in `config.yaml` en de profielen worden vanzelf opnieuw ingelezen.
- Na een nieuwe versie van de app: stop de oude en start de nieuwe.
- Na een update van de webinterface ververs je de pagina met **Cmd+Shift+R** (Windows: **Ctrl+F5**).

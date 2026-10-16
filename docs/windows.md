# Windows

De manager draait ook op Windows 11. Alles werkt hetzelfde als op de Mac: het deck, de webinterface, profielen, bibliotheken en plugins. Wat anders is, staat hieronder.

## Installeren

1. Installeer **Python 3.11 of nieuwer** van [python.org](https://www.python.org/downloads/windows/), met het vinkje **py launcher**.
2. Zet de projectmap op de laptop, bijvoorbeeld met `git clone`.
3. Open PowerShell in de projectmap en voer uit:

   ```
   powershell -ExecutionPolicy Bypass -File tools\windows\install.ps1
   ```

   Dat maakt `.venv` met de pakketten en zet **D200X Manager** in het Startmenu.
4. Zet de tijdzone van de klok in `.env`, net als op de Mac (`TIMEZONE=Europe/Amsterdam`).

## Starten

Start **D200X Manager** vanuit het Startmenu. Er verschijnt een icoon in het systeemvak (rechtsonder, eventueel onder het pijltje). Het menu van dat icoon:

- **Webinterface openen** (ook met een klik op het icoon);
- **Manager herstarten**, **Log tonen** (`%LOCALAPPDATA%\D200X Manager\manager.log`) en **Projectmap tonen**;
- **Starten bij inloggen**;
- **D200X Manager stoppen**.

Stopt de manager, bijvoorbeeld omdat het deck niet is aangesloten, dan start de app hem na 10 seconden opnieuw. Starten zonder systeemvak kan ook: `.venv\Scripts\python -X utf8 d200x_manager.py`.

## Sneltoetsen

- `cmd` is op Windows **Ctrl**. Zo kopieert `cmd+c` op beide systemen. Ook `ctrl` werkt gewoon.
- `alt` (en `option`) is Alt. De Windows-toets heet `win`, bijvoorbeeld `win+e` voor Verkenner.
- `fn` bestaat op Windows niet; `win`, `insert` en `printscreen` bestaan op de Mac niet. Een toets daarmee doet op het andere systeem niets en toont "niet op deze computer".
- **brightnessup** en **brightnessdown** regelen de helderheid van het laptopscherm (via Windows zelf; werkt niet op een losse monitor).

## Apps

Een app is een `.exe` of een snelkoppeling uit het Startmenu (`.lnk`). De app-kiezer toont standaard het Startmenu, en daarnaast Program Files. Een profiel koppel je aan een app net als op de Mac; de manager kijkt welk programma vooraan staat.

## Eén config voor Mac en Windows

`config.yaml` en de profielen kunnen via git op beide computers hetzelfde zijn. Waar een toets per systeem iets anders moet doen, geef je per systeem een waarde:

```
pages:
  1:
    1: {type: app, title: Mail, app: {mac: /Applications/Mail.app, windows: 'C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE'}}
    2: {type: key, title: Apps, keys: {mac: cmd+tab, windows: alt+tab}}
```

Dat kan bij `app` en `keys`, ook bij een lang indrukken (`hold`), en bij het `app:` van een profiel. Bewerk je zo'n toets in de webinterface, dan verandert alleen de waarde van het systeem waarop je werkt.

Een toets met alleen een Mac-app (zoals `/Applications/Mail.app`) toont op Windows zijn titel met "niet op deze computer", en doet daar niets. De rest van de config werkt gewoon.

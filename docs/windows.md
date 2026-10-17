# Windows

De manager draait ook op Windows 11. Alles werkt hetzelfde als op de Mac: het deck, de webinterface, profielen, bibliotheken en plugins. Wat anders is, staat hieronder.

## Installeren

Op Windows bouw je de exe zelf, op de laptop:

1. Installeer **Python 3.11 of nieuwer** van [python.org](https://www.python.org/downloads/windows/), met het vinkje **py launcher**.
2. Zet de projectmap op de laptop, bijvoorbeeld met `git clone`.
3. Open PowerShell in de projectmap en voer uit:

   ```
   powershell -ExecutionPolicy Bypass -File tools\build-windows.ps1
   ```

   Dat maakt `dist\D200X Manager.exe`: één bestand met alles erin.
4. Zet de exe in een eigen map, bijvoorbeeld `C:\D200X Manager\`. Die map wordt de config-map (zie [Installeren](installatie.md)), tenzij je in de webinterface een andere kiest.
5. Start de exe. Bij de eerste start komt de startconfig naast de exe te staan. Zet de tijdzone van de klok in `.env` in die map (`TIMEZONE=Europe/Amsterdam`).

Wil je een snelkoppeling in het Startmenu, sleep de exe dan met de rechtermuisknop naar `%APPDATA%\Microsoft\Windows\Start Menu\Programs` en kies **Snelkoppeling maken**.

## Starten

Na het starten verschijnt een icoon in het systeemvak (rechtsonder, eventueel onder het pijltje). Het menu is hetzelfde als op de Mac; een klik op het icoon opent de webinterface. Het log staat in `%LOCALAPPDATA%\D200X Manager\manager.log`.

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

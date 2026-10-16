# Claude-gebruik

De plugin **Claude usage** toont op het deck hoeveel je van je Claude-abonnement gebruikt hebt: de sessielimiet (5 uur) en de weeklimiet (7 dagen). Het zijn dezelfde cijfers als in het paneel **Account & usage** van Claude Code.

## Instellen

1. Zorg dat je op deze Mac bent ingelogd bij Claude Code.
2. Klik in de webinterface op **Plugins…**, zet het vinkje bij **Claude usage** aan, en klik eventueel op **Verbinding testen**.
3. Sleep een toets uit de bibliotheek **Claude usage** op het deck, of kies bij een toets het type **Claude-gebruik** en de **limiet**.

Er is geen token nodig: de plugin gebruikt de login die Claude Code zelf in de sleutelhanger van macOS bewaart ("Claude Code-credentials"). Hij past die login nooit aan en vernieuwt hem ook niet. Is de login verlopen, gebruik Claude Code dan even; dat vernieuwt hem.

## Wat een toets toont

- de limiet, bijvoorbeeld **Sessie (5u)** of **Week (7d)**;
- het percentage dat je gebruikt hebt;
- een balk: blauw, oranje vanaf 75%, rood vanaf 90%;
- wanneer de limiet weer op nul gaat, bijvoorbeeld **Reset over 14m** of **3d**.

Een druk op de toets haalt de cijfers meteen op (hooguit eens per 30 seconden). Verder ververst de plugin elke 5 minuten; dat stel je in onder **Plugins…** (60 tot 3600 seconden). Bij te veel verzoeken wacht hij vanzelf even.

De limieten **Sonnet (7d)** en **Opus (7d)** bestaan alleen bij abonnementen die ze hebben; anders toont de toets "geen limiet".

## In het bestand

```
pages:
  1:
    4: {type: claude.usage, window: five_hour}
    5: {type: claude.usage, window: seven_day, title: Week}
```

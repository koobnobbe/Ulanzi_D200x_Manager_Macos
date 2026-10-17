# Claude-gebruik

De plugin **Claude usage** toont op het deck hoeveel je van je Claude-abonnement gebruikt hebt: de sessielimiet (5 uur) en de weeklimiet (7 dagen). Het zijn dezelfde cijfers als in het paneel **Account & usage** van Claude Code.

## Instellen

1. Klik in de webinterface op **Plugins…** en zet het vinkje bij **Claude usage** aan.
2. Klik op **Verbinding testen**. Die stelt het script `plugins/claude_usage/statusline.py` in als statusregel van Claude Code (`statusLine` in `~/.claude/settings.json`).
3. Start Claude Code **in de terminal** (`claude`) en stuur een bericht. Daarna staan de cijfers op het deck.

> De statusregel draait alleen in Claude Code in de terminal. De VS Code-extensie heeft geen statusregel, dus wie alleen de extensie gebruikt krijgt geen cijfers. Gebruik je Claude Code in VS Code, zet dan de instelling **Claude Code: Use Terminal** aan; dan draait Claude Code in de terminal van VS Code en werkt het wel.
4. Sleep een toets uit de bibliotheek **Claude usage** op het deck, of kies bij een toets het type **Claude-gebruik** en de **limiet**.

## Hoe het werkt

Claude Code geeft na elk bericht de limieten van je abonnement door aan zijn statusregel. `statusline.py` bewaart ze in `claude_usage.json` in de cache van de app (de map `.cache`) en toont zelf een korte regel onderin Claude Code, bijvoorbeeld `Opus · 5h 23% · 7d 41%`. De plugin leest dat bestand en tekent de toetsen meteen opnieuw als het verandert.

Er gaat dus niets over het netwerk en er is geen login of token nodig. De cijfers zijn zo vers als het laatste bericht in een Claude Code-sessie. Is een limiet intussen gereset, dan toont de toets 0%.

Heb je al een eigen statusregel, dan laat de plugin die staan en zegt hij welk commando je zelf moet instellen. Werkt Claude Code met een API-sleutel in plaats van een abonnement, dan zijn er geen limieten en blijft de toets op "-".

## Wat een toets toont

- de limiet, **Sessie (5u)** of **Week (7d)**;
- het percentage dat je gebruikt hebt;
- een balk: blauw, oranje vanaf 75%, rood vanaf 90%;
- wanneer de limiet weer op nul gaat, bijvoorbeeld **Reset over 14m** of **3d**;
- een rood uitroepteken zolang er nog geen cijfers van Claude Code zijn.

Een druk op de toets leest het bestand opnieuw.

## In het bestand

```
pages:
  1:
    4: {type: claude.usage, window: five_hour}
    5: {type: claude.usage, window: seven_day, title: Week}
```

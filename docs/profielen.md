# Profielen

Een profiel is een complete indeling van het deck: pagina's, toetsen, eventueel draaiknoppen en een achtergrond.

- **default** is het hoofdprofiel. Het staat in `config.yaml` en wordt gebruikt als geen ander profiel past.
- Elk ander profiel is een bestand in de map `profiles/`, bijvoorbeeld `profiles/Finder.yaml`.

## Een profiel maken

Klik links op **+ Nieuw profiel** en geef het een naam (letters, cijfers, spatie, `-` of `_`). Het nieuwe profiel krijgt een pagina met navigatietoetsen.

## Een app koppelen

Rechts van elke profielnaam staat een icoon:

- het icoon van de gekoppelde app, of
- een vakje met **+** als er nog geen app gekoppeld is.

Klik erop om de **profielinstellingen** te openen:

- **App die dit profiel activeert**: kies met **Kies…** een app. Elke app kan maar bij één profiel horen.
- **Achtergrond**: zie [Achtergronden en klok](achtergronden.md).
- De **prullenbak** haalt de koppeling met de app weg. Het profiel zelf blijft bestaan.

Bij **default** staat een knop met **…**. Die opent dezelfde instellingen, maar dan alleen de achtergrond, want default hoort niet bij een app.

## Automatisch wisselen

De manager kijkt elke seconde welke app vooraan staat. Wisselt die, dan:

- wordt het profiel geladen dat aan die app gekoppeld is, of
- wordt **default** geladen als er geen profiel bij die app hoort.

In de terminal zie je bij elke wissel een regel zoals:

```
active app: Finder (profile: Finder)
```

Er is één uitzondering. Heeft een [app-toets](toetsen.md#app-openen) een profiel geladen, dan blijft dat profiel staan, ook als je van app wisselt. In de terminal staat dan `sticky`. Kies je daarna met een profiel-toets een ander profiel, dan wisselt het weer automatisch mee met de apps.

## Wat er in een profielbestand staat

```
app: "/System/Library/CoreServices/Finder.app"
background_image: "backgrounds/bureau.png"
pages:
  1:
    1: {type: key, keys: "cmd+n", title: "New window"}
knobs:
  K1: {index: 0x11, type: key, left: volumedown, right: volumeup}
```

- `app`: de app die dit profiel activeert (optioneel).
- `background_image` of `background_color`: de achtergrond van dit profiel, een afbeelding of een effen kleur (optioneel).
- `pages`: de pagina's en toetsen.
- `knobs`: eigen draaiknoppen (optioneel). Zie [Draaiknoppen](draaiknoppen.md#draaiknoppen-per-profiel).

De apparaat-instellingen (`device`) en de standaardwaarden voor toetsen (`button_defaults`) komen altijd uit `config.yaml`.

## Een profiel verwijderen

Dat kan niet vanuit de webinterface. Verwijder het bestand in `profiles/`. Staat het profiel op dat moment op het deck, kies dan eerst een ander profiel.

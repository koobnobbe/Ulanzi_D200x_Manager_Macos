# Toetsen

Klik in de webinterface op een toets om hem te bewerken. Bovenaan het venster kies je het **type**, daaronder het uiterlijk. Met **Opslaan** wordt de toets meteen op het deck gezet. De prullenbak linksonder maakt de toets leeg.

## Types

| Type | Wat een druk doet | Velden |
|---|---|---|
| **Tekst** (`text`) | Niets, behalve `output` printen als dat is ingevuld. Handig als label. | — |
| **Toetsen** (`key`) | Stuurt een toetscombinatie of een reeks combinaties naar de Mac. | `keys` |
| **App** (`app`) | Opent een app en laadt eventueel een profiel. | `app`, `profile` |
| **Pagina** (`page`) | Gaat naar een andere pagina van het profiel. | `page` |
| **Profiel** (`profile`) | Laadt een ander profiel. | `profile` |

### Toetsen sturen

Een combinatie schrijf je als modifiers en een toets met `+` ertussen, bijvoorbeeld `cmd+c` of `ctrl+shift+tab`. In het venster helpt de keuzelijst **Kies een toets** je op weg.

- **Modifiers**: `cmd`, `ctrl`, `alt` (of `option`), `shift`, `fn`.
- **Toetsen**: `a`–`z`, `0`–`9`, `f1`–`f12`, `enter`, `tab`, `space`, `esc`, `backspace`, `delete`, `forwarddelete`, `up`, `down`, `left`, `right`, `home`, `end`, `pageup`, `pagedown`, en leestekens zoals `,` `.` `/` `;` `'` `[` `]` `-` `=`.
- **Mediatoetsen** (zonder modifiers): `volumeup`, `volumedown`, `mute`, `play`, `next`, `previous`, `brightnessup`, `brightnessdown`.

Een **reeks** combinaties typ je in het venster met komma's: `cmd+a, cmd+c`. Ze worden direct na elkaar verstuurd. In het bestand staat een reeks als lijst: `keys: [cmd+a, cmd+c]`.

> Gewone toetscombinaties hebben toestemming voor Toegankelijkheid nodig. Zie [Installeren en starten](installatie.md#toestemming-voor-toetscombinaties).

### App openen

Kies met **Kies…** een app uit `/Applications` of een andere map. De toets toont dan het icoon van de app, met de titel eronder.

Met **Profiel bij deze app** bepaal je wat er met het profiel gebeurt:

| Keuze | Gevolg |
|---|---|
| automatisch (leeg) | Het profiel dat aan deze app gekoppeld is, wordt geladen. Is er geen, dan blijft het huidige profiel. |
| geen profiel (`none`) | Het profiel verandert niet. |
| een profielnaam | Dat profiel wordt geladen. |

Een profiel dat met een app-toets is geladen, blijft staan als je daarna van app wisselt, totdat je met een profiel-toets een ander profiel kiest. Zie [Profielen](profielen.md#automatisch-wisselen).

### Pagina en profiel

- **Pagina**: `home` (pagina 1), `next`, `previous` of een paginanummer. `next` en `previous` gaan rond: na de laatste pagina komt pagina 1.
- **Profiel**: `default` (het hoofdprofiel in `config.yaml`) of de naam van een ander profiel.

## Uiterlijk

| Veld | Betekenis |
|---|---|
| **Titel** (`title`) | Tekst op de toets. Bij een app staat hij onder het icoon. |
| **Icoon** (`icon`) | Een afbeelding in plaats van tekst of app-icoon. Met **Nieuw…** kies je een png, jpg, ico of icns; die wordt als 192×192 png in `icons/` gezet. |
| **Achtergrond** (`background`) | Achtergrondkleur, bijvoorbeeld `#1a1a2e`. Klik op het veld voor een kleurkiezer. |
| **Tekstkleur** (`color`) | Kleur van de titel. |
| **Lettergrootte** (`font_size`) | Grootte van de titel in pixels, 8–200. |
| **Transparantie** (`transparency`) | 0–100%. Hoe hoger, hoe meer de achtergrond van het profiel door de toets heen schijnt. Zie [Achtergronden en klok](achtergronden.md). |

Velden die je leeg laat, komen uit `button_defaults` in `config.yaml`.

## Lang indrukken

Met **Activeer longpress** geef je een toets een tweede actie voor als je hem minstens 0,6 seconde vasthoudt. Kies het type (`page`, `profile`, `key` of `app`) en de waarde, bijvoorbeeld `default` bij een profiel.

Een toets met een longpress doet pas iets als je hem loslaat: kort loslaten geeft de gewone actie, lang vasthouden de longpress-actie.

## Output

Het veld `output` (alleen in het bestand) print een tekst in de terminal bij elke druk, wat het type ook is. Handig om te testen.

## Voorbeelden in YAML

```
1: {type: key, title: Copy, keys: cmd+c}
2: {type: app, app: /System/Library/CoreServices/Finder.app, title: Finder}
3: {type: key, title: Mute, keys: mute, icon: icons/mute.png}
11: {type: page, page: previous, title: "<"}
12: {type: page, page: home, title: Home, hold: {type: profile, profile: default}}
```

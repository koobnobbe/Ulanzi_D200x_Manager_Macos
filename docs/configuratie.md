# Configuratiebestanden

Alles wat je in de webinterface instelt, staat in gewone tekstbestanden. Je kunt ze ook met een teksteditor bewerken. De manager ziet een wijziging binnen een seconde en laadt het bestand dan opnieuw.

Bevat een bestand een fout, dan blijft de vorige configuratie actief. De foutmelding staat in de terminal en in het rood in de webinterface.

## Mappen en bestanden

| Pad | Inhoud |
|---|---|
| `config.yaml` | Het profiel **default**, de apparaat-instellingen en de standaardwaarden voor toetsen. |
| `profiles/*.yaml` | Eén bestand per profiel. Zie [Profielen](profielen.md). |
| `library/*.yaml` | De bibliotheken. Zie [Bibliotheek en plugins](bibliotheek.md). |
| `library/hidden.json` | Welke bibliotheken verborgen zijn. |
| `icons/` | Iconen voor toetsen, 192×192 png. |
| `backgrounds/` | Achtergronden voor profielen, het klok-venster en de screensaver. |
| `docs/` | Deze documentatie. |
| `.env` | De tijdzone van de klok. |
| `.cache/`, `.build/` | Gegenereerde plaatjes en bestanden voor het deck. Die kun je negeren. |

## config.yaml

```
background_image: "backgrounds/bureau.png"   # achtergrond van default

device:
  brightness: 80
  keep_alive_interval: 1.0
  clock_background: "#000000"                 # kleur achter de klok als toets 14 er geen heeft
  screensaver: "dim"
  screensaver_timeout: 60
  screensaver_brightness: 10
  screensaver_color: "#000000"
  screensaver_image: ""

button_defaults:                              # geldt voor elke toets, ook in profielen
  background: "#1a1a2e"
  color: "#ffffff"
  font_size: 60

pages:
  1:
    1: {type: key, title: Copy, keys: cmd+c}

knobs:
  K1: {index: 0x11, type: key, left: volumedown, right: volumeup, press: mute}
```

| Sectie | Uitleg |
|---|---|
| `background_image` | Achtergrond van het profiel default. Zie [Achtergronden en klok](achtergronden.md). |
| `device` | Helderheid, screensaver en keep-alive. Zie [Apparaat en screensaver](apparaat.md). |
| `button_defaults` | Standaardwaarden voor alle toetsen. Een toets hoeft alleen te noemen wat afwijkt. |
| `pages` | De pagina's met toetsen. Zie [Pagina's](paginas.md) en [Toetsen](toetsen.md). |
| `knobs` | De draaiknoppen. Zie [Draaiknoppen](draaiknoppen.md). |

## Alle velden van een toets

| Veld | Bij type | Waarde |
|---|---|---|
| `type` | — | `text` (standaard), `key`, `app`, `page` of `profile` |
| `title` | alle | tekst op de toets |
| `keys` | `key` | combinatie zoals `cmd+c`, of een lijst `[cmd+a, cmd+c]` |
| `app` | `app` | pad naar een `.app` |
| `profile` | `app`, `profile` | profielnaam, `default`, of bij een app ook `none` |
| `page` | `page` | `home`, `next`, `previous` of een nummer |
| `icon` | alle | pad naar een afbeelding, bijvoorbeeld `icons/copy.png` |
| `background` | alle | achtergrondkleur, bijvoorbeeld `"#1a1a2e"` |
| `color` | alle | tekstkleur |
| `font_size` | alle | lettergrootte in pixels, 8–200 |
| `transparency` | alle | 0–100 |
| `background_image` | alleen toets 14 | afbeelding achter de klok |
| `hold` | alle | actie bij lang indrukken, bijvoorbeeld `{type: profile, profile: default}` |
| `output` | alle | tekst die bij een druk in de terminal wordt geprint |

## Tips voor handmatig bewerken

- Zet kleuren tussen aanhalingstekens: `"#1a1a2e"`. Zonder aanhalingstekens ziet YAML de `#` als begin van commentaar.
- Een pad met spaties mag gewoon: `app: /Applications/Brave Browser.app`.
- De webinterface schrijft een toets altijd op één regel. Commentaar aan het eind van een regel die de webinterface aanpast, kan verdwijnen.

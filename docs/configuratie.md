# Configuratiebestanden

Alles wat je in de webinterface instelt, staat in gewone tekstbestanden. Je kunt ze ook met een teksteditor bewerken. De manager ziet een wijziging binnen een seconde en laadt het bestand dan opnieuw.

Bevat een bestand een fout, dan blijft de vorige configuratie actief. De foutmelding staat in de terminal en in het rood in de webinterface.

## Mappen en bestanden

| Pad | Inhoud |
|---|---|
| `config.yaml` | Het profiel **default**, de apparaat-instellingen en de standaardwaarden voor toetsen. |
| `profiles/*.yaml` | Eén bestand per profiel. Zie [Profielen](profielen.md). |
| `library/*.yaml` | De bibliotheken. Zie [Bibliotheken](bibliotheek.md). |
| `library/hidden.json` | Welke bibliotheken verborgen zijn. |
| `plugins/` | Plugins, zoals Home Assistant. Zie [Plugins](plugins.md). |
| `plugins.local.yaml` | Instellingen en geheimen van plugins, per machine en niet in git. |
| `icons/` | Iconen voor toetsen, 192×192 png. |
| `backgrounds/` | Achtergronden voor profielen, het klok-venster en de screensaver. |
| `docs/` | Deze documentatie. |
| `lang/` | De teksten van de webinterface, per taal. Zie [Taal](#taal). |
| `.env` | De tijdzone van de klok. |
| `.cache/`, `.build/` | Gegenereerde plaatjes en bestanden voor het deck (bij de app: in `~/Library/Caches/D200X Manager` of `%LOCALAPPDATA%\D200X Manager`). Die kun je negeren. |

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

ui:
  language: "nl"                              # taal van de webinterface; zonder deze regel Engels
```

| Sectie | Uitleg |
|---|---|
| `background_image` / `background_color` | Achtergrond van het profiel default: een afbeelding of een effen kleur. Zie [Achtergronden en klok](achtergronden.md). |
| `device` | Helderheid, screensaver en keep-alive. Zie [Apparaat en screensaver](apparaat.md). |
| `button_defaults` | Standaardwaarden voor alle toetsen. Een toets hoeft alleen te noemen wat afwijkt. |
| `pages` | De pagina's met toetsen. Zie [Pagina's](paginas.md) en [Toetsen](toetsen.md). |
| `knobs` | De draaiknoppen. Zie [Draaiknoppen](draaiknoppen.md). |
| `ui` | Instellingen van de webinterface, zoals de taal. Zie [Taal](#taal). |
| `page_settings` | Naam en achtergrond per pagina. Zie [Pagina's](paginas.md#pagina-instellingen). |

## Alle velden van een toets

| Veld | Bij type | Waarde |
|---|---|---|
| `type` | — | `text` (standaard), `key`, `app`, `page` of `profile` |
| `title` | alle | tekst op de toets |
| `keys` | `key` | combinatie zoals `cmd+c`, of een lijst `[cmd+a, cmd+c]` |
| `app` | `app` | pad naar een `.app`, of een link die macOS opent, zoals `raycast://…` |
| `profile` | `app`, `profile` | profielnaam, `default`, of bij een app ook `none` |
| `page` | `page` | `home`, `next`, `previous` of een nummer |
| `icon` | alle | pad naar een afbeelding, bijvoorbeeld `icons/copy.png` |
| `background` | alle | achtergrondkleur, bijvoorbeeld `"#1a1a2e"` |
| `color` | alle | tekstkleur |
| `font_size` | alle | lettergrootte in pixels, 8–200 |
| `transparency` | alle | 0–100 |
| `background_image` | alleen toets 14 | afbeelding achter de klok |
| `hold` | alle | actie bij lang indrukken, bijvoorbeeld `{type: profile, profile: default}` |
| `text` | `text` | tekst die een druk op de toets plakt in de app vooraan (via het klembord, dat daarna zijn tekst terugkrijgt) |
| `output` | alle | tekst die bij een druk in de terminal wordt geprint |

## Taal

Alle teksten van de webinterface en de meldingen die daarin verschijnen, staan per taal in `lang/`, bijvoorbeeld `lang/nl.yaml`. De documentatie staat daar niet in.

De taal kies je in de webinterface met **Scherm config…** in de bovenbalk. Er zijn bestanden voor Engels, Nederlands, Frans, Duits en Spaans; de keuzelijst toont elk bestand in `lang/`. De keuze wordt opgeslagen onder `ui: language:` in `config.yaml`. Staat daar niets, dan is de webinterface Engels.

Een andere taal toevoegen:

1. Kopieer `lang/en.yaml` naar bijvoorbeeld `lang/it.yaml`.
2. Vertaal de teksten, ook `language_name` bovenaan: dat is de naam in de keuzelijst. Laat de sleutels links van de dubbele punt en de namen tussen accolades, zoals `{name}`, staan.
3. Kies de taal onder **Scherm config…**.

Ontbreekt een tekst in de nieuwe taal, dan wordt de Engelse gebruikt. Wijzigingen in een taalbestand zie je na het verversen van de pagina, zonder herstart.

## Tips voor handmatig bewerken

- Zet kleuren tussen aanhalingstekens: `"#1a1a2e"`. Zonder aanhalingstekens ziet YAML de `#` als begin van commentaar.
- Een pad met spaties mag gewoon: `app: /Applications/Brave Browser.app`.
- De webinterface schrijft een toets altijd op één regel. Commentaar aan het eind van een regel die de webinterface aanpast, kan verdwijnen.

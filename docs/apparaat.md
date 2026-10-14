# Apparaat en screensaver

## Helderheid

De schuif **Helderheid** in de bovenbalk zet het deck op 0–100. Je kunt de helderheid ook aan een draaiknop geven met het type `device_brightness`. Zie [Draaiknoppen](draaiknoppen.md).

> De schuif en de draaiknop worden niet opgeslagen. Na een herstart begint het deck weer op de waarde van `brightness` onder `device` in `config.yaml`.

## Apparaat-instellingen

Klik in de bovenbalk op **Apparaat…**. De instellingen worden opgeslagen onder `device:` in `config.yaml` en gelden voor alle profielen.

### Screensaver

| Modus | Wat er gebeurt |
|---|---|
| **Uit** | Het deck blijft altijd aan. |
| **Firmware-screensaver** | De eigen screensaver van het deck. Die start na ongeveer 30 seconden; hoe hij eruitziet kun je niet instellen. |
| **Dimmen** | Na de wachttijd gaat het deck naar de screensaver-helderheid. |
| **Effen kleur** | Na de wachttijd worden alle toetsen één kleur en gaat de helderheid omlaag. |
| **Afbeelding** | Na de wachttijd komt één afbeelding over alle toetsen en gaat de helderheid omlaag. |

Bij Dimmen, Effen kleur en Afbeelding stel je ook in:

- **Na (seconden inactief)**: hoe lang het deck onaangeroerd moet zijn, 5–3600 seconden.
- **Helderheid tijdens screensaver**: 0–100.
- **Kleur** of **Afbeelding**, afhankelijk van de modus.

Druk op een willekeurige toets of draaiknop om de screensaver te stoppen. Die eerste druk doet verder niets, zodat je niet per ongeluk iets start. Daarna komen de toetsen en de helderheid terug.

### Keep-alive

Zonder regelmatig signaal van de Mac gaat het deck na ongeveer 30 seconden naar zijn eigen screensaver. De manager stuurt daarom regelmatig een signaal. **Keep-alive interval** bepaalt hoe vaak, 0,2–10 seconden. Standaard is dat 1 seconde, en dat hoef je meestal niet te veranderen.

In de modus Firmware-screensaver stopt de keep-alive, zodat de eigen screensaver van het deck kan starten.

## In het bestand

```
device:
  brightness: 80
  keep_alive_interval: 1.0
  screensaver: "dim"            # off, firmware, dim, color of image
  screensaver_timeout: 60
  screensaver_brightness: 10
  screensaver_color: "#000000"
  screensaver_image: ""
```

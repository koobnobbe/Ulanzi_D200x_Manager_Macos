# Draaiknoppen

Het deck heeft drie draaiknoppen: **K1**, **K2** en **K3**, van links naar rechts. Elke knop kent drie acties: naar links draaien, naar rechts draaien en indrukken.

Klik in de webinterface op een draaiknop in de afbeelding om hem te bewerken. Houd je de muis even boven een knop, dan zie je wat hij nu doet.

## Types

| Type | Links / Rechts / Druk |
|---|---|
| `text` | De tekst wordt in de terminal geprint. Handig om te testen. |
| `key` | Toetscombinaties, met dezelfde schrijfwijze als bij [Toetsen](toetsen.md#toetsen-sturen). Bijvoorbeeld `volumedown`, `volumeup` en `mute`. |
| `device_brightness` | Links en rechts maken het deck donkerder of lichter. **Stap** bepaalt hoeveel per klik (standaard 10). Indrukken doet niets. |

## In het bestand

```
knobs:
  K1: {index: 0x11, type: key, left: volumedown, right: volumeup, press: mute}
  K2: {index: 0x12, type: key, left: brightnessdown, right: brightnessup}
  K3: {index: 0x13, type: device_brightness, step: 10}
```

`index` is het nummer waarmee het deck de knop meldt. Laat het staan zoals het is.

## Draaiknoppen per profiel

De knoppen in `config.yaml` gelden voor alle profielen. Een profiel kan een eigen `knobs:`-sectie hebben.

> Let op: heeft een profiel een eigen `knobs:`-sectie, dan gelden de knoppen uit `config.yaml` niet meer voor dat profiel, ook niet de knoppen die er niet in staan. Bewerk je in een profiel één knop via de webinterface, dan krijgt dat profiel zo'n sectie met alleen die knop. Neem de andere knoppen dan ook op in het profiel als je ze wilt houden.

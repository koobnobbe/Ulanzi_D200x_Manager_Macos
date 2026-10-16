# Home Assistant

Met de plugin **Home Assistant** bedien je lampen en schakelaars vanaf het deck, zie je live of ze aan staan, toon je standen zoals een temperatuur, en dim je een lamp met een draaiknop.

## Instellen

1. Maak in Home Assistant een **long-lived access token**: klik linksonder op je profiel, ga naar **Beveiliging** en kies **Token aanmaken**. Kopieer het token; je ziet het maar één keer.
2. Klik in de webinterface op **Plugins…**.
3. Vul bij Home Assistant het **adres** in, bijvoorbeeld `http://homeassistant.local:8123`, en plak het **token**.
4. Klik op **Verbinding testen**. Werkt het, dan staat er welke versie van Home Assistant je hebt.
5. Klik op **Opslaan** en zet het vinkje bij de plugin aan.

De status rechtsboven in het venster wordt groen (**verbonden**) zodra de verbinding er is.

> Gebruik je Home Assistant met een eigen (self-signed) certificaat via `https://`, zet dan **TLS-certificaat controleren** uit.

De instellingen staan in `plugins.local.yaml`, per machine en niet in git. Het token wordt nooit naar de browser gestuurd: laat je het veld leeg, dan blijft het opgeslagen token staan.

## Toetsen

Open een toets en kies een van de tabbladen van Home Assistant. Bij **Entity** typ je een naam of een entity-id; de lijst met voorstellen komt rechtstreeks uit Home Assistant.

| Type | Wat een druk doet | Wat de toets toont |
|---|---|---|
| **Lamp of schakelaar** (`ha.toggle`) | Zet de lamp of schakelaar aan of uit | Een lamp: geel als hij aan is (of in zijn eigen kleur), met de helderheid in procenten. Een schakelaar: groen als hij aan is. Grijs als hij uit is |
| **Stand tonen** (`ha.state`) | Niets | De stand of waarde, met eenheid, bijvoorbeeld `19.5 °C` |

De titel is de naam uit Home Assistant, tenzij je zelf een titel invult. De achtergrondkleur, transparantie en lang indrukken werken zoals bij andere toetsen.

Verandert de stand in Home Assistant (ook als iemand anders de lamp aanzet), dan wordt alleen die toets op het deck bijgewerkt, meestal binnen een fractie van een seconde.

### Badges

| Badge | Betekenis |
|---|---|
| rood met **!** | Geen verbinding met Home Assistant. De plugin probeert het steeds opnieuw. |
| rood met **?** | Home Assistant kent de entity niet, of meldt hem als niet beschikbaar. |

## Dimmer op een draaiknop

Klik op een draaiknop en kies **Home Assistant: dimmer (lamp)**. Kies de lamp en de **stap** in procenten (1–50, standaard 10).

- Draai naar rechts: lichter. Draai naar links: donkerder.
- Indrukken: aan of uit.

## In het bestand

```
pages:
  1:
    5: {type: ha.toggle, entity: light.woonkamer}
    6: {type: ha.toggle, entity: switch.ventilator, title: Fan}
    7: {type: ha.state, entity: sensor.buiten_temperatuur, title: Buiten}
knobs:
  K2: {index: 0x12, type: ha.dimmer, entity: light.woonkamer, step: 10}
```

Een toets van Home Assistant mag ook in een bibliotheek staan.

## Als het niet werkt

| Melding | Oplossing |
|---|---|
| Home Assistant accepteert dit token niet | Maak een nieuw token en sla het op. Na een fout token wacht de plugin een minuut voor hij het opnieuw probeert. |
| … is niet bereikbaar | Controleer het adres en of deze Mac Home Assistant kan bereiken. |
| Het TLS-certificaat wordt niet vertrouwd | Zet **TLS-certificaat controleren** uit, of gebruik een geldig certificaat. |
| De toets toont "Home Assistant staat uit" | Zet de plugin aan onder **Plugins…**. |

Wat er gebeurt, staat ook in de terminal, bijvoorbeeld `Home Assistant connected (2026.10.0, 312 entities)`.

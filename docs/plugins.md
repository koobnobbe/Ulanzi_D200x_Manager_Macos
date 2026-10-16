# Plugins

Een plugin is lokale code in de map `plugins/` die nieuwe soorten toetsen en draaiknoppen toevoegt, met eigen instellingen en live standen. Er wordt niets gedownload: alleen wat in `plugins/` staat, wordt geladen.

> Plugins zijn iets anders dan **bibliotheken**. Een bibliotheek is een lijst kant-en-klare toetsen in een YAML-bestand; zie [Bibliotheken](bibliotheek.md). Een plugin is code.

Meegeleverd: [Home Assistant](home-assistant.md), [Claude-gebruik](claude-usage.md) en [Websites](websites.md).

## Het Plugins-venster

Klik in de bovenbalk op **Plugins…**. Per plugin zie je:

- een vinkje om hem **aan of uit** te zetten;
- de **status**: verbonden, verbinden, fout of uit, met een toelichting;
- de **instellingen**, met **Verbinding testen** en **Opslaan**.

Staat een plugin uit of start hij niet, dan blijft de rest gewoon werken. Toetsen van die plugin tonen dan dat de plugin uit staat, en doen niets.

## Instellingen per machine

De instellingen en geheimen van plugins staan in `plugins.local.yaml`, naast `config.yaml`. Dat bestand staat niet in git, zodat elke machine (thuis, werk) zijn eigen adres en token kan hebben. Alleen jij kunt het lezen (bestandsrechten 0600).

```
homeassistant:
  enabled: true
  url: http://homeassistant.local:8123
  token: eyJ…
  verify_ssl: true
```

## Een plugin maken

Een plugin is een map in `plugins/` met:

| Bestand | Inhoud |
|---|---|
| `plugin.yaml` | Naam, versie, de module en klasse, de instellingen en de toetstypes met hun velden |
| `plugin.py` | Een klasse die erft van `plugins.Plugin` |
| `lang/<taal>.yaml` | De teksten; in de app staan ze onder `plugin.<id>.…` |

In `plugin.yaml` beschrijf je per toetstype de velden: `entity` (een id als `light.woonkamer`, eventueel beperkt tot domeinen), `number` (met `min` en `max`) of tekst. De manager controleert die velden zelf, ook als de plugin uit staat, en bouwt er de formulieren in de webinterface mee.

De klasse kan deze methodes gebruiken:

| Methode | Doel |
|---|---|
| `start()` / `stop()` | Verbinding openen en sluiten (async) |
| `status()` | Status voor het Plugins-venster |
| `actions(type, toets, event)` | Wat een druk of draai doet; een actie mag async zijn |
| `render(type, toets)` | Het plaatje van een toets, met live stand |
| `watches(type, toets)` | Wat een toets toont; roep `ctx.refresh({id})` aan als dat verandert |
| `call(actie, data)` | Verzoeken van de webinterface, zoals een lijst voor een kiezer of een verbindingstest |

`ctx.refresh` tekent alleen de toetsen opnieuw die dat id tonen, en stuurt alleen die naar het deck.

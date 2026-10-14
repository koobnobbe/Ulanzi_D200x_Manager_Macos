# Problemen oplossen

## "No Ulanzi D200 found"

De manager vindt het deck niet en stopt.

- Controleer of het deck met USB is aangesloten en aan staat.
- Sluit Ulanzi Studio af.
- Probeer een andere USB-poort of kabel.

## Toetscombinaties doen niets

Mediatoetsen werken wel, maar `cmd+c` en dergelijke niet? Dan mist de toestemming voor Toegankelijkheid. Zie [Installeren en starten](installatie.md#toestemming-voor-toetscombinaties). Herstart daarna de manager.

Werkt een reeks zoals **Morgen** niet goed in een app, controleer dan of die app vooraan staat en of de sneltoetsen kloppen met het menu van die app.

## De klok geeft de verkeerde tijd

Zet de juiste tijdzone in `.env`. Zie [Installeren en starten](installatie.md#tijdzone-van-de-klok).

## Het deck valt in slaap

- Staat de screensaver op **Firmware-screensaver**? Dan stopt de keep-alive en slaapt het deck na ongeveer 30 seconden. Kies een andere modus bij **Apparaat…**.
- Draait de manager nog? Zonder manager valt het deck na ongeveer 30 seconden in zijn eigen screensaver.

Zie [Apparaat en screensaver](apparaat.md).

## Het profiel wisselt niet mee met de app

- Is de app gekoppeld aan het profiel? Rechts van de profielnaam staat dan het icoon van de app. Zie [Profielen](profielen.md#een-app-koppelen).
- Kijk in de terminal. Bij elke wissel staat er welke app vooraan staat en welk profiel erbij hoort, bijvoorbeeld `active app: Finder (profile: Finder)`.
- Staat er `sticky`? Dan heeft een app-toets het profiel vastgezet. Kies met een profiel-toets een ander profiel om dat op te heffen.

## Een wijziging is niet te zien

- Staat er een rode foutmelding onder het deck? Dan is de configuratie niet geladen. Los de fout op; de vorige configuratie blijft zolang actief.
- Bewerk je een profiel dat niet actief is? Dan zie je het pas op het deck als dat profiel actief wordt.
- Na een update van de code: herstart de manager.
- Na een update van de webinterface: ververs de pagina met **Cmd+Shift+R**.

## De webinterface opent niet

Staat in de terminal `web interface not started`? Dan is poort 8765 bezet, meestal door een tweede manager die nog draait. Stop die en start opnieuw.

## Ruwe gebeurtenissen van het deck bekijken

Voor onderzoek naar onbekende knoppen of gebeurtenissen is er een hulpscript. Stop eerst de manager en start dan:

```
python3 tools/sniff.py 60
```

Het script print 60 seconden lang alles wat het deck stuurt.

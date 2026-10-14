# D200X Manager

De D200X Manager stuurt een **Ulanzi D200X** stream controller aan vanaf een Mac, zonder Ulanzi Studio. Je bepaalt zelf wat elke toets en draaiknop doet, en het deck wisselt automatisch van indeling als je van app wisselt.

## Wat kan het?

- **Toetsen** die een toetscombinatie sturen, een app openen, naar een andere pagina of een ander profiel gaan, of alleen tekst tonen. Zie [Toetsen](toetsen.md).
- **Lang indrukken** voor een tweede actie op dezelfde toets.
- **Draaiknoppen** voor volume, helderheid of eigen toetscombinaties. Zie [Draaiknoppen](draaiknoppen.md).
- **Pagina's** om meer toetsen kwijt te kunnen dan er op het deck passen. Zie [Pagina's](paginas.md).
- **Profielen per app**: een profiel wordt vanzelf actief zodra de bijbehorende app vooraan komt. Zie [Profielen](profielen.md).
- **Achtergronden** per profiel, transparante toetsen en een eigen klok-venster. Zie [Achtergronden en klok](achtergronden.md).
- **Screensaver** die dimt of een kleur of afbeelding toont. Zie [Apparaat en screensaver](apparaat.md).
- **Bibliotheek** met kant-en-klare toetsen die je op het deck sleept, bijvoorbeeld voor BusyCal. Zie [Bibliotheek en plugins](bibliotheek.md).

## Het deck in het kort

Het deck heeft 13 toetsen met een scherm, een breed klok-venster, twee ronde knoppen en drie draaiknoppen. In de configuratie hebben de toetsen deze nummers:

```
  1   2   3   4   5
  6   7   8   9  10
 11  12  13  [ klok (14) ]

 (16) (17)   K1   K2   K3
```

- **1–13** hebben een eigen scherm.
- **14** is het brede klok-venster. Het reageert op een druk, en je kunt er een eigen achtergrond voor kiezen.
- **16 en 17** zijn de ronde knoppen linksonder. Ze hebben geen scherm, maar je kunt er wel een actie aan geven.
- **K1–K3** zijn de draaiknoppen. Draaien naar links, draaien naar rechts en indrukken kunnen elk een eigen actie hebben.

## Snel aan de slag

1. Installeer en start de manager: [Installeren en starten](installatie.md).
2. Open de webinterface op `http://127.0.0.1:8765`: [De webinterface](webinterface.md).
3. Klik op een toets in de afbeelding van het deck en kies wat hij moet doen.

> Alles wat je in de webinterface instelt, wordt opgeslagen in gewone YAML-bestanden. Zie [Configuratiebestanden](configuratie.md) als je liever met een teksteditor werkt.

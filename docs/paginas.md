# Pagina's

Een profiel kan meerdere pagina's hebben, elk met een eigen indeling van de toetsen. Zo heb je meer toetsen dan er op het deck passen.

## Wisselen

- Op het deck wissel je met toetsen van het type **Pagina** (`page`): `next`, `previous`, `home` of een paginanummer. Zie [Toetsen](toetsen.md#pagina-en-profiel).
- In de webinterface klik je op het tabblad van een pagina. Bij het actieve profiel springt het deck mee.

Bij het laden van een profiel begint het deck altijd op pagina 1.

## Een pagina toevoegen

Klik op **+ Nieuwe pagina**. De nieuwe pagina krijgt meteen een paar navigatietoetsen:

| Toets | Actie |
|---|---|
| 11 | Vorige pagina (`<-`) |
| 12 | Pagina 1 (`Home`) |
| 13 | Volgende pagina (`->`) |
| 14 (klok-venster) | Naar het profiel `default` |
| 16 | Pagina 1 |
| 17 | Volgende pagina |

Die kun je daarna gewoon aanpassen of weghalen.

## Pagina-instellingen

Rechts naast de tabbladen staat de knop **config** met een tandwiel. Die opent de instellingen van de pagina die je bekijkt:

- **Naam**: staat op het tabblad in plaats van "Pagina 2". Maximaal 30 tekens.
- **Achtergrond**: een eigen afbeelding of effen kleur voor alleen deze pagina, met een kleurkiezer voor de kleur. Kies je niets, of klik je op **Achtergrond verwijderen**, dan geldt de achtergrond van het profiel. Zie [Achtergronden en klok](achtergronden.md).
- **Volgorde**: schuif de pagina een plek naar links of rechts. Dat gebeurt meteen. De toetsen en instellingen gaan mee, en toetsen die naar die pagina gaan, worden aangepast. Schuif je een pagina naar de eerste plek, dan wordt het de startpagina.
- **Prullenbak**: verwijdert de pagina met al haar toetsen. Toetsen die naar die pagina gingen, gaan daarna naar pagina 1. Pagina 1 kan niet weg.

De instellingen staan in het bestand van het profiel onder `page_settings:`:

```
page_settings:
  2: {name: Media, background_image: "backgrounds/media.png"}
  3: {name: Werk, background_color: "#203040"}
```

> Toetsen die door het schuiven of verwijderen worden aangepast, worden opnieuw weggeschreven. Commentaar aan het eind van zo'n regel verdwijnt dan.

## In het bestand

```
pages:
  1:
    1: {type: key, title: Copy, keys: cmd+c}
    13: {type: page, page: next, title: ">"}
  2:
    1: {type: key, title: Paste, keys: cmd+v}
    13: {type: page, page: previous, title: "<"}
```

Toetsen die niet op een pagina staan, blijven leeg en tonen de achtergrond van het profiel.

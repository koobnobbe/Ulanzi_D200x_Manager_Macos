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

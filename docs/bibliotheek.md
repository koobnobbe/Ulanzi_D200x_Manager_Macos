# Bibliotheken

De bibliotheek staat rechts in de webinterface. Hij bevat kant-en-klare toetsen die je op het deck sleept. Elke groep in de bibliotheek is een bestand in de map `library/`.

## Werken met de bibliotheek

| Actie | Hoe |
|---|---|
| Een toets op het deck zetten | Sleep een item uit de bibliotheek naar een toets. Hij komt op de pagina en in het profiel dat je bekijkt. |
| Een toets bewaren | Sleep een toets van het deck naar het bibliotheekpaneel. Hij komt in de groep **template**. |
| Verplaatsen naar een andere groep | Sleep een item naar de titel van een andere groep. |
| Verwijderen | Sleep een item naar de prullenbak bovenaan het paneel. |
| Een nieuwe groep maken | Klik op **+ Nieuwe bibliotheek**. |
| In- of uitklappen | Klik op de titel van een groep. Je browser onthoudt dit. |

## Meegeleverde bibliotheken

| Bibliotheek | Inhoud |
|---|---|
| **Agenda** | Toetsen voor BusyCal: Vandaag, Morgen, Gisteren, Deze week, Volgende week, Dag-, Week- en Maandweergave, nieuwe afspraak of taak, zoeken en meer. |
| **Applications** | Een paar apps om te openen. |
| **functionkeys** | F1 tot en met F12. |
| **sound** | Volume, mute, afspelen, volgende en vorige, helderheid van het scherm. |
| **template** | Toetsen die je zelf hebt bewaard. Bovenaan het bestand staat een overzicht van alle velden. |

De Agenda-toetsen gebruiken de sneltoetsen van BusyCal. Sommige sturen een reeks: **Morgen** gaat naar de dagweergave (`cmd+1`), naar vandaag (`cmd+t`) en één dag verder (`cmd+right`).

## Eigen iconen in een zip

Gebruiken toetsen in een bibliotheek een eigen icoon-bestand (zoals `icon: icons/mute.png`), dan staan die bestanden in een zip naast het yaml-bestand, met dezelfde naam: bij `library/Shottr.yaml` hoort `library/Shottr.zip`. Iconen van apps zijn geen bestanden en staan er niet in.

- De zip wordt vanzelf bijgehouden als je toetsen toevoegt, verplaatst of verwijdert. Een bibliotheek zonder eigen iconen heeft geen zip.
- Sleep je een toets uit de bibliotheek op het deck, dan wordt het icoon uit de zip naar `icons/` gekopieerd. Staat er in `icons/` al een bestand met die naam, dan blijft dat staan.
- Wil je een bibliotheek delen, geef dan het yaml-bestand en de zip samen door.

## Bibliotheken aan en uit

Klik in de bovenbalk op **Bibliotheken…** voor een lijst van alle bibliotheken. (Code die nieuwe soorten toetsen toevoegt, zoals Home Assistant, staat onder [Plugins](plugins.md).)

- **Vinkje aan**: de bibliotheek staat in het paneel.
- **Vinkje uit**: de bibliotheek is verborgen. Het bestand blijft bestaan, en toetsen die al op het deck staan blijven werken.

Welke bibliotheken verborgen zijn, staat in `library/hidden.json`.

### Een bibliotheek importeren

Klik in het venster Bibliotheken op **Importeren…** en kies een `.yaml`-bestand. Heeft de bibliotheek eigen iconen, kies dan tegelijk de `.zip` met dezelfde naam. Het bestand wordt eerst gecontroleerd. Alleen een geldig bestand wordt naar `library/` gekopieerd; anders zie je in het venster wat er mis is, bijvoorbeeld:

```
toets 3 (Morgen): onbekende toetscombinatie: cmd+ü
```

De naam van de bibliotheek wordt de bestandsnaam zonder `.yaml`. Bestaat er al een bibliotheek met die naam, dan wordt het bestand niet geïmporteerd.

## Bestandsformaat

Een bibliotheekbestand heeft bovenaan alleen `buttons:`, met daaronder een lijst toetsen. Elke toets staat op een eigen regel die begint met twee spaties, een streepje en een spatie:

```
# Commentaar mag overal.
buttons:
  - {type: key, title: Vandaag, keys: [cmd+1, cmd+t]}
  - {type: app, app: /Applications/BusyCal.app, title: BusyCal}
  - {title: Label, background: "#203040"}
```

Een toets heeft dezelfde velden als op het deck: zie [Toetsen](toetsen.md). Een lege bibliotheek schrijf je als `buttons: []`.

Bij het importeren wordt gecontroleerd dat:

- het bestand geldige YAML is, met alleen `buttons:` bovenaan;
- elke toets een bekend type heeft (`text`, `key`, `app`, `page` of `profile`) en alleen bekende velden;
- toetscombinaties bestaan en apps op deze Mac staan;
- kleuren geldig zijn, de lettergrootte tussen 8 en 200 ligt en de transparantie tussen 0 en 100;
- iconen en afbeeldingen bestaan, in `icons/` of in de meegegeven zip; de zip mag alleen png-bestanden bevatten;
- een `page`-toets een `page` heeft en een `profile`-toets een `profile`;
- de `hold`-actie aan dezelfde regels voldoet.

> Staan de toetsen in het bestand over meerdere regels verdeeld, dan zet de import ze om naar één toets per regel. Commentaar in dat bestand gaat dan verloren.

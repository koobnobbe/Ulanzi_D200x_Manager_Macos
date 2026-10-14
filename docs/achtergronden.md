# Achtergronden en klok

## Achtergrond per profiel

Elk profiel heeft een eigen achtergrond over het hele scherm van het deck: een **afbeelding** of een **effen kleur**. Kies je er geen, dan is de achtergrond **zwart**. Een profiel neemt de achtergrond van default niet over.

Instellen gaat via de profielinstellingen: klik links op het icoon rechts van de profielnaam (bij default op **…**) en kies bij **Achtergrond**:

- **Afbeelding**: kies er een uit de lijst of voeg er een toe met **Nieuw…**.
- **Effen kleur**: typ een kleur zoals `#203040`, of klik op het veld of het kleurvlakje voor een kleurkiezer.
- **Achtergrond verwijderen** zet de keuze terug op geen (zwart). Klik daarna op **Opslaan**.

- Met **Nieuw…** kies je een afbeelding op je Mac. Die wordt verkleind tot maximaal 1960 pixels en als png in `backgrounds/` gezet. Daarna staat hij in de keuzelijst, ook voor andere profielen.
- De afbeelding wordt passend gemaakt voor het scherm: hij wordt geschaald tot hij het hele scherm vult, en wat uitsteekt wordt aan de randen weggesneden.
- Lege toetsen, waar niets op staat, tonen de achtergrond.
- Een pagina kan een eigen achtergrond hebben (afbeelding of kleur), die voor die pagina in de plaats komt van die van het profiel. Zie [Pagina's](paginas.md#pagina-instellingen).

In het profielbestand staat het als `background_image: "backgrounds/naam.png"` of `background_color: "#203040"`. Voor default staat het bovenaan `config.yaml`.

## Transparante toetsen

Een toets met een eigen achtergrondkleur bedekt de achtergrond van het profiel. Met **Transparantie** in het toets-venster laat je de achtergrond erdoorheen schijnen:

| Waarde | Resultaat |
|---|---|
| 0 | De toetskleur is helemaal dekkend (standaard). |
| 50 | Half toetskleur, half achtergrond. |
| 100 | Alleen de achtergrond is zichtbaar. |

Alleen de achtergrond van de toets wordt doorzichtig. De titel, het app-icoon en een eigen icoon-afbeelding blijven volledig zichtbaar. Heeft een icoon-png zelf doorzichtige delen, dan zie je daar de achtergrondkleur van de toets; bij een hogere transparantie schijnt ook daar de achtergrond van het profiel door.

Wil je dat alle toetsen een beetje doorzichtig zijn, zet dan `transparency` onder `button_defaults` in `config.yaml`.

## Het klok-venster

Het brede vlak rechtsonder is het klok-venster. Het deck tekent daar zelf de tijd op. De achtergrond van dat vlak hoort bij **toets 14**: klik in de webinterface op het klok-venster om hem in te stellen.

- **Achtergrond**: de kleur achter de klok.
- **Klok-venster afbeelding**: een afbeelding over het hele brede vlak. Dit veld zie je alleen bij toets 14.
- **Transparantie**: laat de achtergrond van het profiel door de kleur of afbeelding heen schijnen.

Dit geldt per pagina: elke pagina kan een eigen klok-achtergrond hebben. Stel je niets in, dan gebruikt het venster de kleur uit `clock_background` onder `device` in `config.yaml`, of zwart als die er niet is.

> Wil je de achtergrond van het profiel achter de klok zien, zet dan de transparantie van toets 14 op 100.

### Een toets in plaats van de klok

Geef je toets 14 een **titel** of **icoon**, dan verdwijnt de klok. Op de linkerhelft van het venster staat dan die toets, net als op het deck.

### De tijd klopt niet

De klok gebruikt de tijdzone uit `.env`. Zie [Installeren en starten](installatie.md#tijdzone-van-de-klok).

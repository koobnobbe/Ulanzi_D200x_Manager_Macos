# Websites

De plugin **Websites** maakt toetsen die een website openen. De toets toont het icoon van de site, met de naam eronder.

## Instellen

1. Klik in de webinterface op **Plugins…** en zet het vinkje bij **Websites** aan. Er is niets in te stellen.
2. Kies bij een toets het type **Website** en vul het **webadres** in, bijvoorbeeld `nos.nl` of `https://github.com/koobnobbe`. Zonder `https://` wordt dat er vanzelf voor gezet.
3. Kies eventueel een **browser**: Safari, Google Chrome, Firefox, Arc, Microsoft Edge of Brave. Standaard opent de site in je standaardbrowser.

Zonder titel staat de naam van de site op de toets (`nos.nl`); met een titel die titel.

## Het icoon

De plugin haalt het icoon één keer op bij de site zelf: het apple-touch-icon, het icoon uit de pagina of `/favicon.ico`. Het komt in `favicons/` in de cache van de app (de map `.cache`) en wordt daarna niet meer opgehaald. Tot het binnen is, of als een site geen bruikbaar icoon heeft, toont de toets de eerste letter van de site op een gekleurde tegel.

Een nieuw icoon nodig, bijvoorbeeld omdat de site een nieuw logo heeft? Verwijder het bestand van die site uit die map `favicons/` en zet de plugin uit en weer aan.

## In het bestand

```
pages:
  1:
    4: {type: web.open, url: nos.nl}
    5: {type: web.open, url: https://github.com/koobnobbe, title: GitHub, browser: safari}
```

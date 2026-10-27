# Unical Support · Design System & UI Kit

Laboratorio standalone, lazy-loaded su `/design-system`, accessibile senza login. Dopo la promozione globale del tema, il catalogo resta un laboratorio locale; l’architettura operativa è documentata in `docs/ARCHITECTURE.md`. Tutte le interazioni sono simulazioni locali: nessun invio di email, modifica delle impostazioni applicative o caricamento al backend.

## Identità

I colori sono stati campionati dal simbolo originale `logo.png`: rosso `#B61918`, grigio `#9E9E9D`, nero `#000000`. La variante verticale allegata mostra un rosso leggermente diverso (`#B41B22`); il simbolo più semplice è il riferimento per i token. Le scale 50–900 sono derivate, non colori ufficiali aggiuntivi. L’indaco `#6352B9` è una scelta funzionale per l’AI, distinta dal brand; verde, ambra e rosso segnalano gli stati di processo con testo e icone.

Superfici chiare, neutri freddi, bordi sottili, ombre discrete e font di sistema evitano download e mantengono leggibilità e densità. Il grigio del logo è decorativo; testi e controlli usano neutri più scuri. I codici nella palette documentano i token base, anche durante l’anteprima ad alto contrasto.

## Isolamento e accessibilità

- I token del catalogo sono dichiarati su `:host` in `ds-tokens.css` per isolare gli esperimenti. Gli stessi token di base sono stati promossi a `:root` in `frontend/public/styles/_tokens.css` per le pagine operative.
- Gli stili usano l’incapsulamento Angular predefinito. La pagina governa il proprio viewport e contenitore di scorrimento.
- L’unica modifica al contenitore applicativo esclude sidebar e widget dal laboratorio. `Location.path()` riconosce l’URL iniziale prima di `NavigationEnd`, evitando il montaggio transitorio della sidebar e le sue richieste API.
- Routing e guard delle altre pagine restano invariati.
- “Aspetto e accessibilità” apre un drawer locale: contrasto elevato con bordi da 2 px, densità confortevole e movimento ridotto. Le preferenze del laboratorio si azzerano uscendo dalla pagina. Le preferenze globali dell’app si gestiscono invece in Impostazioni tramite `ThemePreferencesService`, con persistenza in localStorage.
- Modale e drawer usano `<dialog>.showModal()` per rendere inerte lo sfondo, gestire il focus e supportare Escape. I tab supportano frecce, Home ed End; input e controlli hanno etichette, errori collegati e focus visibile.
- `prefers-reduced-motion` viene rispettato automaticamente. Gli stati non dipendono soltanto dal colore.
- La dropzone conserva solo i nomi dei file e valida estensione/dimensione (10 MB); non legge né trasmette il contenuto.

## File creati

In `frontend/src/app/features/design-system/`:

- `design-system.component.ts` — shell, navigazione, palette e preferenze via Signals.
- `design-system.component.html` — foundations e pannello accessibilità.
- `design-system.component.css` — struttura, sidebar, topbar e reset locali.
- `ds-tokens.css` — token e varianti locali di accessibilità.
- `ds-identity.css` — hero e showcase del logo.
- `ds-foundations.css` — palette, tipografia, spacing, radius e ombre.
- `ds-preferences.css` — drawer delle preferenze e feedback copia.
- `ds-layout-responsive.css` — adattamenti tablet e mobile.
- `ds-playground.component.ts` — stati e interazioni dimostrative.
- `ds-playground.component.html` — buttons, forms, dati, feedback e overlay.
- `ds-controls.css` — pulsanti, stati e struttura degli esempi.
- `ds-forms.css` — input, editor, multi-select, switch e chip.
- `ds-upload-models.css` — radio cards, dropzone e lista file.
- `ds-data.css` — badge, fonti, confidence e thread email.
- `ds-feedback.css` — callout, toast, skeleton e viste segmentate.
- `ds-dialog.css` — modale e drawer di contesto.
- `ds-icon.component.ts` — icone SVG locali, senza dipendenze.
- `design-system.component.spec.ts` — 11 test di preferenze e interazioni.
- `design-system-routing.spec.ts` — test di apertura diretta e isolamento.
- `README.md` — questo documento.

In `frontend/public/design-system/`:

- `logo-symbol.png` — copia inalterata del simbolo fornito.
- `logo-horizontal.png` — copia inalterata del logotipo orizzontale fornito.

File esistenti modificati: `frontend/src/app/app.routes.ts` e `frontend/src/app/app.component.ts`.

## Verifica

Dalla cartella `frontend`:

```sh
npm run build
CHROME_BIN='/Applications/Brave Browser.app/Contents/MacOS/Brave Browser' npm test -- --watch=false --browsers=ChromeHeadless --karma-config=karma.conf.cjs
```

Le dipendenze già dichiarate sono state ripristinate senza modificare manifest o lockfile. Il browser Chromium disponibile in questo ambiente è Brave. La build mantiene i budget originali. Il Design System e il renderer `html2canvas` vengono caricati come chunk lazy separati, e il bundle iniziale rientra nel budget. Resta l’avviso CommonJS di `html2canvas`. I fogli di stile locali sono divisi per responsabilità e rispettano il budget CSS esistente.

# Unical Support · UI globale e master-detail

## Risultato

Le pagine operative adottano la palette Unical, una shell compatta e liste a righe. Revisione email, Base documentale e Categorie aprono un pannello affiancato soltanto dopo una selezione o un’azione di creazione. Le impostazioni separano le preferenze personali dalla configurazione degli agenti AI.

## Componenti aggiornati

- `AppComponent`: shell a viewport intero; il laboratorio e il login mantengono il proprio layout. La navigazione mobile rende inerte il contenuto sottostante.
- `SideNavbarComponent`: brand e navigazione allineati al catalogo, stato attivo con bordo completo rosato, voce padre espandibile per tutte le email e cinque sotto-voci con conteggi delle viste caricate e filtro tramite query parameter `status`, profilo con email su due righe e impostazioni nel footer, modalità compressa e drawer mobile con gestione del focus.
- `ReviewDashboardComponent`: ricerca locale, filtri nella sidebar, sotto-voci selezionate senza box aggiuntivi; righe con avatar pastello, stato, categorie e riferimento monospace, dettaglio con email originale, diagnostica e editor. Le risposte inviate sono in sola lettura. Le modifiche alla bozza sopravvivono ai refresh della stessa conversazione; il cambio di selezione richiede conferma quando ci sono modifiche non salvate. I pulsanti vengono disabilitati durante le operazioni.
- `DocumentManagerComponent`: ricerca per nome, URL, contenuto o categoria; filtro categoria nella topbar; upload di file locali nel pannello di creazione; dettaglio con testo completo e modifica del link della fonte e delle categorie. La cancellazione conserva la conferma esistente.
- `CategoryManagerComponent`: elenco ricercabile e form nel dettaglio per creazione/modifica; feedback di salvataggio e conferma di eliminazione esistente.
- `ModelSettingsComponent`: area Aspetto e accessibilità con anteprima e applicazione immediata; area Modelli AI con card Classificatore e Risponditore e lo stesso contratto di salvataggio.
- `CategoryMultiSelectComponent`: stile condiviso, checkbox native e pulsanti di rimozione realmente utilizzabili da tastiera, senza controlli interattivi annidati nel trigger.
- `FeedbackButtonComponent`: FAB scuro a pillola in basso a destra; su desktop si posiziona sopra le azioni del dettaglio tramite ResizeObserver, su mobile rimane nascosto durante il dettaglio modale; dialog coerente col tema. Il renderer dello screenshot viene caricato solo all’apertura del flusso.

## Elementi condivisi creati

- `frontend/src/app/core/services/theme-preferences.service.ts`
- `frontend/src/app/core/services/shell-ui.service.ts`
- `frontend/src/app/shared/components/ds-icon/ds-icon.component.ts`
- `frontend/src/app/shared/components/workspace-header/workspace-header.component.ts`
- `frontend/src/app/shared/components/detail-panel.directive.ts`
- `frontend/public/styles/_ui.css`
- `frontend/public/styles/_workspace.css`

Il file `frontend/public/styles/_tokens.css` promuove i token del laboratorio a `:root` e mantiene alias per le variabili precedenti. `frontend/src/styles.css` importa i nuovi stili condivisi. L’icona del laboratorio rimane disponibile tramite un export di compatibilità.

## Layout e accessibilità

Su desktop il layout usa CSS Grid, con una lista fluida e un pannello di dettaglio. Sui monitor grandi la lista è limitata a circa 420 px. Lista e corpo del dettaglio scorrono indipendentemente; header e azioni rimangono visibili.

Sotto 1024 px lo stesso dettaglio occupa il viewport, viene identificato come dialog modale, rende inerte la lista, sposta il focus sui controlli del pannello, circoscrive Tab e supporta Escape. Alla chiusura il focus torna al controllo di apertura quando ancora presente. La sidebar mobile ha comportamento analogo. Le verifiche visive sono state effettuate anche a 390 × 844 px, senza overflow orizzontale nelle tre feature.

`ThemePreferencesService` usa Signals, valida il contenuto salvato e persiste le preferenze nella chiave `unical-support.theme.v1`. Gli attributi sul documento sono:

- `data-contrast`: `standard` / `high` (bordi da 2 px, colori più scuri, ombre eliminate).
- `data-density`: `compact` / `comfortable` (padding delle righe e altezza dei controlli).
- `data-reading`: `normal` / `large` (testo email e bozza da 14 / 18 px).
- `data-motion`: `full` / `reduced`; la preferenza di movimento ridotto del sistema viene sempre rispettata.
- `data-theme`: `light`, punto di estensione per un’eventuale futura palette scura.

I problemi di accesso a localStorage non bloccano l’interfaccia. Il catalogo `/design-system` conserva le proprie variabili locali per la sperimentazione.

## Contratti e limiti dei dati

Le guard e i contratti degli agenti AI restano invariati; gli endpoint documentali sono stati aggiornati per l’upload esclusivo da file e il link della fonte modificabile. Il polling delle email, il controllo manuale Gmail, l’invio e l’escalation mantengono i flussi precedenti. Il salvataggio della bozza usa l’endpoint già disponibile e conserva lo stato corrente; solo l’azione esplicita di approvazione richiede `SENT`.

Le API email attuali non forniscono timestamp, motivazioni specifiche di escalation, punteggi di confidence o frammenti recuperati: la UI ne indica l’assenza. Non vengono inventati dati diagnostici né aggiunte richieste a endpoint inesistenti. I contatori riguardano le viste caricate (l’API esistente limita la lista a 100 record), non un totale server non disponibile. Anche il test di connessione degli agenti non è esposto: lo stato viene mostrato come non verificato.

Per i documenti `POST /api/documents/upload` richiede un file locale e accetta il solo `reference_url` opzionale. `PUT /api/documents/{id}` aggiorna categorie e link: omettere il link lo conserva, `null` o stringa vuota lo rimuove. La migrazione `c8f4a1e6d203` conserva i riferimenti e rimuove il campo legacy `link`. Il worker non scarica pagine web; il retrieval AI usa il riferimento corrente del documento, anche quando viene rimosso.

## Test e build

Suite frontend: 43 test superati in Chromium Headless, inclusi i test precedenti. I nuovi test coprono persistenza e validazione delle preferenze, storage non disponibile, ricerca locale, selezione e chiusura del dettaglio, protezione delle bozze, errore Gmail, prevenzione di invii ripetuti, payload API di documenti/categorie/modelli e focus/tastiera del pannello mobile, deep link dei filtri email, navigazione dalla sidebar e ripristino del filtro quando si annulla lo scarto di una bozza modificata.

```sh
cd frontend
npm run build
CHROME_BIN='/Applications/Brave Browser.app/Contents/MacOS/Brave Browser' npm test -- --watch=false --browsers=ChromeHeadless --karma-config=karma.conf.cjs
```

La build di produzione completa senza errori e rispetta i budget CSS e il budget iniziale: circa 386 kB. Resta l’avviso CommonJS della dipendenza esistente `html2canvas`, ora in un chunk lazy di circa 203 kB. Non sono stati modificati manifest, lockfile o budget per aggirare le verifiche.

Durante la verifica nel browser sono stati controllati i dati esistenti, le preferenze locali e l’apertura dei form/dialog; non sono state inviate email, segnalazioni o modifiche ai record applicativi.

## Rifinitura responsive e link unico (15 ottobre 2026)

La rotta canonica di revisione è `/review`; `/review-hub` rimane un redirect compatibile che conserva i query parameter. La voce padre mostra la vista completa e un chevron con controllo accessibile `aria-expanded`; le cinque sotto-voci selezionate evidenziano soltanto testo, pallino e numero.

Searchbox e azione primaria misurano 38 px di altezza. La ricerca prende lo spazio restante tramite flex; sotto 768 px il pulsante misura 38 × 38 px, con label nascosta ma nome accessibile e tooltip. Verificati 1440 × 900 e 375 × 812 px su tutte e tre le pagine senza overflow orizzontale.

In modalità standard i contenitori interni e il divisore del profilo non hanno bordi; le righe usano divisori `#F1F5F9`, gli input `#E2E8F0`, la ricerca un bordo trasparente. Alto contrasto ripristina contorni da 2 px attraverso i token `--ds-container-stroke`, `--ds-divider` e `--ds-search-border`.

Pytest: 40 test e 14 subtest superati nel container worker, inclusi test reali PostgreSQL di upgrade/downgrade e sincronizzazione dei metadati dei chunk, compatibilità dei file già accodati e mancato download dei vecchi task web. Runner pytest installato solo in `/tmp/unical-test-tools` nel container. Comando: `docker compose -f docker-compose.dev.yml exec -T -e PYTHONPATH=/tmp/unical-test-tools:/app worker python -m pytest tests -q`.

Migrazione applicata al database locale dopo backup `/tmp/unical-before-single-source-link.dump`; documento esistente conservato. Worker e scheduler ricaricati per usare lo schema aggiornato. Le preferenze di contrasto provate nel browser sono state ripristinate.

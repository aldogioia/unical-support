# OPERATIONS

Eseguire i comandi dalla radice del repository. Per la produzione usare sempre progetto, file Compose e override del manifest di deploy: un Compose lanciato con un nome progetto diverso può selezionare volumi diversi.

## Avvio in sviluppo

Prerequisiti: Docker Engine/Desktop con Compose v2, file `.env` locale e chiavi dei provider utilizzati. Non copiare i secret di produzione nel repository.

```bash
docker compose -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.dev.yml run --rm --no-deps backend alembic upgrade head
docker compose -f docker-compose.dev.yml ps
```

Su un database ancora vuoto i servizi possono segnalare tabelle mancanti fino al completamento di Alembic. Dopo la migrazione:

```bash
docker compose -f docker-compose.dev.yml restart backend worker beat
```

Frontend: `http://localhost:4200`; backend: `http://localhost:8000`. Il proxy Angular inoltra API e statici al backend Docker. `SHOW_DOCS=true` abilita Swagger/ReDoc; in produzione sono disabilitati per default. Non pubblicare le porte di sviluppo su una macchina esposta.

Il backend e Angular ricaricano il codice locale; worker e Beat richiedono il riavvio dopo modifiche Python. Per fermare lo sviluppo senza eliminare dati usare `docker compose -f docker-compose.dev.yml stop`.

## Creazione degli account

Non esiste una password universale. Per creare un account nel database dell'ambiente selezionato:

```bash
docker compose -f docker-compose.dev.yml exec backend python create_user.py
```

Lo script chiede email, password nascosta con conferma e ruolo (`admin` o `user`). Rifiuta email duplicate e password inferiori a otto caratteri. In produzione eseguire lo stesso comando `exec backend python create_user.py` con il prefisso Compose del manifest, da una sessione SSH interattiva. Non inserire password nella riga di comando o nei log. Il messaggio finale dello script indica localhost anche in produzione: accedere invece all'indirizzo effettivo dell'installazione.

## Scelta del provider email

`MAIL_PROVIDER=gmail_api` è il default. `MAIL_PROVIDER=smtp` legge via IMAP e invia via SMTP. Backend e worker devono usare lo stesso provider e la stessa casella.

### Gmail API e OAuth

Il consenso interattivo si esegue da una macchina con browser, con `credentials.json` autorizzato per la casella:

```bash
python -m app.listener.gmail_client --reauth
```

L'applicazione non apre un browser nei processi server: un token assente/non rinnovabile produce un errore. Non stampare o committare `token.json` e `credentials.json`. Lo script di deploy non carica quelli del computer locale: conserva i file presenti sul server o nei container esistenti in `<remote-dir>/.deploy/runtime/`. Le credenziali sono montate in sola lettura; il token è scrivibile per il rinnovo. Un nuovo consenso richiede l'aggiornamento dei file remoti e la ricreazione di backend/worker: la semplice sostituzione atomica di un file bind-mounted non aggiorna l'inode visto dai vecchi container.

### IMAP/SMTP

In sviluppo aggiungere a `.env` i valori di `.env.mail.example`, compresa la password. Con Gmail utilizzare una password per app, se consentita dall'organizzazione; la normale password dell'account non sostituisce questo requisito. In produzione la password vive in `/home/operatore/secrets/mail_password` e l'overlay `docker-compose.smtp.yml` la monta in backend e worker.

| Variabile | Default / significato |
| --- | --- |
| `MAIL_USERNAME` | Indirizzo completo della casella |
| `MAIL_FROM` | Se vuoto usa MAIL_USERNAME |
| `MAIL_IMAP_HOST`, `MAIL_IMAP_PORT` | imap.gmail.com, 993 |
| `MAIL_IMAP_SECURITY`, `MAIL_IMAP_FOLDER` | ssl, INBOX |
| `MAIL_SMTP_HOST`, `MAIL_SMTP_PORT` | smtp.gmail.com, 465 |
| `MAIL_SMTP_SECURITY` | ssl; per STARTTLS configurare anche la porta |
| `MAIL_TIMEOUT_SECONDS`, `MAIL_FETCH_LIMIT` | 30 secondi per operazione, 50 messaggi |
| `MAIL_PASSWORD_SECRET_FILE` | Percorso del secret SMTP di produzione |

Sono consentiti TLS implicito (`ssl`) e STARTTLS obbligatorio (`starttls`); non sono previsti login in chiaro. Per SMTP STARTTLS usare normalmente la porta 587. Dopo modifiche all'ambiente Docker ricreare i container, perché `restart` non applica nuove variabili Compose.

IMAP usa BODY.PEEK e marca il messaggio letto solo dopo l'acquisizione, senza EXPUNGE. Gmail IMAP usa X-GM-MSGID per mantenere gli identificativi delle API Gmail; altri provider usano casella, cartella, UIDVALIDITY e UID. Cambiare casella/cartella o UIDVALIDITY può rendere non riutilizzabili i vecchi identificativi. Per rispondere il messaggio originale deve essere ancora reperibile nella cartella configurata. I provider generici non ricevono una copia automatica nella cartella Inviati.

## Monitoraggio e diagnosi

In sviluppo:

```bash
docker compose -f docker-compose.dev.yml ps
docker compose -f docker-compose.dev.yml logs --tail=100 beat
docker compose -f docker-compose.dev.yml logs --tail=100 worker
docker compose -f docker-compose.dev.yml exec -T backend celery -A app.core.celery_app inspect ping --timeout 10
docker compose -f docker-compose.dev.yml exec -T backend celery -A app.core.celery_app inspect registered
```

In produzione sostituire il prefisso con quello registrato in `manifest.json`. I log possono contenere mittenti, contenuto o errori del provider: non pubblicarli integralmente senza rimuovere dati personali e token.

| Sintomo | Verifica / azione |
| --- | --- |
| Nessuna email acquisita | Un solo Beat attivo; worker su polling_queue; casella, token/password e stato del polling |
| “Controllo già in corso” | Attendere il job o la scadenza della prenotazione di 660 s; non eliminare indiscriminatamente chiavi Redis |
| Email FAILED | Retry nel dettaglio o nella vista Errori; il batch gestisce al massimo 100 righe per volta |
| Invio fallito con bozza revisionata | Usare “Riprova invio”; non rigenerare il testo approvato |
| Conflitto 409 | Confrontare la versione server; caricarla oppure mantenere esplicitamente il testo locale |
| Job fermo | Attendere lo sweeper ogni 15 minuti; controllare worker, broker e prenotazioni prima di intervenire |
| LLM locale non raggiungibile | Tunnel sul server, URL nelle Impostazioni, worker host e secret loopback |
| Documento needs_review | Leggere review_notes e correggere il documento; non presumere che sia indicizzato |
| Documento pending troppo a lungo | Log document_queue: alcuni errori di estrazione restano da diagnosticare nei log |
| Nessun link nella risposta | Verificare reference_url del documento; un nome senza URL non è una citazione valida |
| Confidence N/D | Metrica non disponibile; non significa necessariamente errore o confidenza zero |

Non eseguire aggiornamenti SQL indiscriminati sugli stati delle email: aggirerebbero revisioni, proprietà manuale e generazioni dei job. La documentazione architetturale descrive i controlli in [ARCHITECTURE](ARCHITECTURE.md).

## Backup e conservazione

In sviluppo:

```bash
docker compose -f docker-compose.dev.yml exec -T db pg_dump -U postgres -d unical_support -Fc > /percorso/protetto/unical-support.dump
docker compose -f docker-compose.dev.yml exec -T db pg_restore --list < /percorso/protetto/unical-support.dump
```

Il dump contiene anche i vettori PostgreSQL. In produzione lo script usa utente e database effettivi del container/secrets, non i valori di sviluppo, e controlla il catalogo del dump con pg_restore. È una verifica strutturale, non un ripristino completo: provare periodicamente il restore su un database separato.

Conservare anche upload ancora necessari, file OAuth, configurazione/secrets e modalità di attivazione del tunnel. Lo script salva il backup sul server, non su uno storage esterno: organizzare una copia protetta fuori macchina e una retention. Non cancellare automaticamente release e immagini di rollback prima di aver verificato l'aggiornamento.

## Test e build

Per i soli script di deploy non servono Docker o dipendenze applicative:

```bash
python3 tests/test_deploy.py
python3 scripts/deploy.py --dry-run --build all --migrate
```

Per la suite backend installare le dipendenze di sviluppo in un ambiente di test. L'immagine worker non include pytest per default. Con la stack locale già attiva:

```bash
docker compose -f docker-compose.dev.yml run --rm --no-deps worker sh -c 'pip install --quiet --target /tmp/unical-test-tools pytest httpx && PYTHONPATH=/tmp/unical-test-tools:/app python -m pytest tests -q'
```

I test PostgreSQL creano database temporanei; richiedono quindi un'utenza di test con permesso CREATEDB. Alcuni test usano namespace Redis isolati. Non eseguire la suite completa contro la produzione.

```bash
docker compose -f docker-compose.dev.yml exec -T frontend npm run build
docker compose -f docker-compose.dev.yml run --rm --no-deps -p 9876:9876 frontend sh -c 'npm ci --no-audit --no-fund && npm test -- --watch=false --karma-config=karma.conf.cjs'
```

Per Karma collegare un browser a `http://localhost:9876/`; se Chrome è installato nel relativo ambiente, passare `--browsers=ChromeHeadless`. L'immagine frontend standard non include Chrome. Il warning CommonJS di html2canvas è noto e non blocca la build.

Le prove live `tests/smoke_language_live.py` richiedono il modello configurato e possono consumare quota; usano retrieval sintetico, senza salvare o inviare email. La verifica del 27 ottobre 2026 aveva superato 105 test backend, 87 frontend, build e cinque casi live. Per il deploy sono stati aggiunti test separati: questi esiti storici non attestano una prova su una VPS.

Rigenerazione del client dopo modifiche alle API:

```bash
docker compose -f docker-compose.dev.yml exec -T frontend npm run generate-api:docker
```

Anteprima statica del template, senza invio:

```bash
docker compose -f docker-compose.dev.yml exec -T backend python scripts/preview_email.py
```

Output: [assets/email-preview.html](assets/email-preview.html). La preview interattiva nel Review Hub usa lo stesso renderer; i testi dell'esempio statico non sono istruzioni amministrative reali.

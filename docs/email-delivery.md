# Risposte dinamiche e impaginazione email

Aggiornamento del 24 ottobre 2026.

## Flusso applicativo

L'agente risponditore dispone soltanto di ricerca nella Knowledge Base, salvataggio della bozza ed escalation. Genera il testo da zero e deve consultare le fonti documentali. Non esistono più modelli SQLAlchemy, schemi Pydantic, servizi, endpoint o funzioni del client OpenAPI per le risposte preconfezionate. Restano soltanto i riferimenti necessari nelle migrazioni storiche e nei test di rimozione/rollback.

La bozza contiene testo semplice, senza markup HTML o note automatiche. Il prompt richiede paragrafi su righe continue e interruzioni esplicite solo fra paragrafi e punti di elenco. `normalize_email_text` unisce le interruzioni singole accidentali, mantiene i paragrafi e le voci di elenchi puntati/numerati e unisce le continuazioni dei singoli punti. La stessa pulizia viene applicata al testo revisionato dall'operatore prima del salvataggio e dell'invio.

La lingua e la nota di trasparenza sono salvate nei campi nullable `emails.response_language` e `emails.ai_disclaimer`. Le traduzioni predefinite includono italiano, inglese, spagnolo, francese, tedesco e portoghese; per altre lingue il tool richiede la traduzione al modello. Le impostazioni linguistiche già esistenti continuano a essere applicate.

La nota di generazione assistita e revisione umana è separata dal testo della bozza e viene mostrata, all’invio, sopra il corpo della risposta. I disclaimer riconosciuti nelle vecchie bozze vengono separati durante il rendering e sostituiti dalla nota corrente, inferendo la lingua dal testo precedente quando possibile; altrimenti si usa la lingua di fallback configurata. Le vecchie righe del database non vengono riscritte in massa.

## Layout e invio

`app/services/email_renderer.py` effettua l'escaping del contenuto e converte solo URL HTTP/HTTPS in collegamenti. Produce paragrafi ed elenchi semantici, preservando la numerazione, senza accettare HTML dal modello o dall'operatore.

L'email usa tabelle di presentazione, stili inline, un contenitore da 640 px, misura di lettura massima di 72ch, carattere Arial di 16 px con interlinea 1.65, bordo rosso `#B61918` e un riquadro di trasparenza separato, sotto il logo e prima del saluto: fondo grigio chiaro, testo grigio di 11 px in corsivo, senza accenti viola. Le regole responsive riducono la spaziatura sui telefoni; il layout include un contenitore condizionale per Outlook. Il logo è la copia invariata di quello già presente nel design system, in `app/assets/unical-logo.png`.

Il messaggio Gmail è `multipart/alternative`: testo semplice con nota in apertura, seguito da una parte `multipart/related` con HTML e logo PNG inline tramite Content-ID. Non richiede il download di un logo remoto. `threadId`, `In-Reply-To`, i riferimenti precedenti e il Message-ID originale vengono mantenuti. Il contenuto rimane UTF-8.

Il renderer viene chiamato solo nel percorso d'invio dopo l'approvazione; salvare una bozza non invia un messaggio. L'editor operativo e il componente modale applicano wrapping naturale, max-width 80ch e interlinea 1.65, con una nota sull'impaginazione finale. L'anteprima fornita è un artefatto offline, non una nuova funzione interattiva nel Review Hub.

## Migrazione

Revisione nuova: `d4a7e2b9f610`, padre: `c8f4a1e6d203`. Script: `alembic/versions/d4a7e2b9f610_remove_canned_responses.py`.

L'upgrade aggiunge i metadati nullable alle email, elimina `template_category`, `templates` e il tipo enum PostgreSQL `templatestatus`. Non modifica categorie, documenti, embedding o il testo delle email esistenti. Le tabelle dei template erano vuote nell'ambiente locale. È stato salvato il backup completo `/private/tmp/unical-support-before-canned-removal-2026-10-24.dump` prima dell'upgrade.

Il downgrade ricrea lo schema dei vecchi template, ma NON ne ripristina i contenuti eliminati e rimuove i nuovi metadati di consegna. Per recuperare contenuti precedenti occorre il backup. Il rollback dello schema è stato verificato su database temporanei, senza effettuarlo sul database attivo.

Per un altro ambiente di sviluppo:

```sh
docker compose -f docker-compose.dev.yml exec -T backend alembic current
docker compose -f docker-compose.dev.yml exec -T db pg_dump -U postgres -d unical_support -Fc > /percorso/backup-prima-rimozione.dump
docker compose -f docker-compose.dev.yml exec -T backend alembic upgrade head
docker compose -f docker-compose.dev.yml exec -T backend alembic check
docker compose -f docker-compose.dev.yml exec -T frontend npm run generate-api:docker
docker compose -f docker-compose.dev.yml restart worker frontend
```

La migrazione è già inclusa: non generare una nuova revisione duplicata. Se si riproduce l'autogenerazione su una copia del codice e un database alla revisione padre, il comando di base è `alembic revision --autogenerate -m "remove canned responses and add delivery metadata"`; il tipo enum e il downgrade vanno comunque revisionati manualmente.

Per un rollback dalla revisione nuova:

```sh
docker compose -f docker-compose.dev.yml stop backend worker beat
docker compose -f docker-compose.dev.yml run --rm --no-deps backend alembic downgrade -1
```

Ripristinare una versione del codice compatibile prima di riavviare: il codice nuovo richiede i metadati email aggiunti. In produzione ricostruire prima le immagini, fermare gli scrittori del vecchio codice, eseguire `alembic upgrade head` con una nuova immagine backend e poi avviare backend/worker aggiornati. Rimuovere le tabelle mentre un worker vecchio sta ancora elaborando risposte può causare errori.

## Test e anteprima

Dipendenze di sviluppo: `requirements-dev.txt`. Nell'immagine worker già installata è stato sufficiente aggiungere pytest; per un ambiente nuovo installare l'intero file delle dipendenze di sviluppo.

```sh
docker compose -f docker-compose.dev.yml exec -T worker python -m pytest tests -q
docker compose -f docker-compose.dev.yml exec -T frontend npm run build
docker compose -f docker-compose.dev.yml run --rm --no-deps -p 9876:9876 frontend npm run test -- --watch=false --karma-config=karma.conf.cjs
```

Per l'ultimo comando collegare il browser a `http://localhost:9876`; con Chrome installato è possibile passare invece `--browsers=ChromeHeadless`. Il container temporaneo termina dopo la suite.

Anteprima offline, con logo incorporato soltanto per facilitare la consultazione locale:

```sh
docker compose -f docker-compose.dev.yml exec -T backend python scripts/preview_email.py
```

Il file generato è `docs/email-preview.html`. I messaggi inviati usano il logo CID, non un data URL. Il testo dell'anteprima è dimostrativo e non descrive procedure reali.

Verifiche: 50 test backend e 43 test Angular superati, build di produzione riuscita, `alembic check` senza differenze. La suite include rimozione dei vecchi endpoint/modelli, upgrade e downgrade, paragrafi ed elenchi, escaping HTML, link, nota multilingua, logo inline e struttura MIME con threading Gmail. Anteprima verificata nel browser su desktop a 960 px e mobile a 390 px, senza overflow orizzontale. Non sono stati eseguiti invii reali né test nativi su Gmail, Outlook o Apple Mail: le verifiche MIME usano un servizio Gmail simulato. Il warning CommonJS di html2canvas e quelli di configurazione Alembic/secrets sono preesistenti e non bloccano i test.

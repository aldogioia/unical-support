> Aggiornamento 15 ottobre 2026: il codice corrente usa la revisione `c8f4a1e6d203`, successiva a quella descritta sotto. Il campo `link` è stato rimosso; `reference_url` è l’unico riferimento, modificabile tramite PUT. L’upload richiede un file locale e non accetta più la modalità web. La nuova migrazione conserva la citazione esplicita, recupera i link legacy quando mancanti e aggiorna i chunk. Il downgrade alla revisione precedente ricrea `link` (max 500 caratteri), mantenendo la citazione completa in `reference_url`. Backup locale prima dell’upgrade: `/tmp/unical-before-single-source-link.dump`. Il resto del documento registra la migrazione precedente.

# Migrazione reference_url e attivazione delle funzionalità

## Modifica introdotta

Revisione: `b7e2f6c8d901`, padre: `a3c9d2f4b7e1`.

La tabella `documents` riceve `reference_url VARCHAR(2048) NULL`, senza default e senza vincoli NOT NULL. Il campo legacy `link` resta invariato. I link HTTP/HTTPS già presenti vengono copiati nel nuovo campo; i documenti senza link restano con NULL. La migrazione aggiunge `reference_url` e `source_name` ai metadati dei chunk esistenti che possiedono `document_id`, senza rigenerare gli embedding. Se il Vector Store non esiste ancora, quella parte viene saltata.

Il retrieval recupera anche i dati del documento dal database: i vecchi chunk senza questi metadati restano utilizzabili. Non è necessario ricaricare i documenti. Un chunk legacy senza `document_id` può essere usato come testo, ma non può essere associato automaticamente a un documento: non viene inventato un link.

Il parametro multipart `url` continua a identificare la pagina da importare (o il link legacy del file). Il nuovo parametro opzionale `reference_url` identifica il link da citare; se assente si usa `url`. Un `reference_url` da solo non avvia un download: occorre un file oppure `url`. Si validano schema HTTP/HTTPS, hostname, lunghezza e assenza di credenziali; la protezione SSRF esistente resta applicata agli URL effettivamente scaricati.

`alembic/env.py` esclude dall'autogenerazione le due tabelle gestite da LangChain (`langchain_pg_collection`, `langchain_pg_embedding`), così Alembic non propone di cancellarle perché non appartengono a `Base.metadata`.

## Stato dell'ambiente locale al 14 ottobre 2026

Docker Compose era già avviato. Il database `unical_support` conteneva le tabelle vettoriali ma nessuna tabella applicativa né revisione Alembic applicata. È stato salvato un backup in `/private/tmp/unical-support-before-reference-url.dump`, quindi sono state applicate le migrazioni preesistenti fino ad `a3c9d2f4b7e1`, generata la nuova revisione e applicato `upgrade head`. Il backup precede anche l'inizializzazione dello schema applicativo.

Il database attivo ora è alla revisione `b7e2f6c8d901`. Non eseguire nuovamente `revision` per questa modifica: lo script è già incluso nel repository. Per altri ambienti serve soltanto `upgrade head`, dopo le verifiche seguenti.

## Verifiche e backup prima della migrazione

Eseguire dalla radice del progetto, usando il file Compose dell'ambiente corretto:

```sh
docker compose -f docker-compose.dev.yml ps
docker compose -f docker-compose.dev.yml exec -T backend alembic current
docker compose -f docker-compose.dev.yml exec -T backend alembic heads
docker compose -f docker-compose.dev.yml exec -T backend alembic history --verbose
docker compose -f docker-compose.dev.yml exec -T db psql -U postgres -d unical_support -c "SELECT count(*) AS documents_before FROM documents;"
docker compose -f docker-compose.dev.yml exec -T db pg_dump -U postgres -d unical_support -Fc > /private/tmp/unical-support-pre-migration.dump
```

Se `documents` non esiste e `alembic current` non mostra una revisione, il database è nuovo: `upgrade head` crea l'intero schema. Se invece ci sono tabelle applicative e manca la revisione, verificare il loro allineamento prima di procedere; non usare `alembic stamp head` per saltare le migrazioni.

Conservare il backup fuori dal repository, con accesso limitato: include i dati applicativi. Su database grandi, pianificare una finestra adeguata per gli aggiornamenti dei metadati. Non lanciare migrazioni concorrenti.

## Generazione dello script: procedura usata e futura

Comando CLI standard, dopo aver aggiornato il modello SQLAlchemy e portato il database alla revisione precedente:

```sh
alembic revision --autogenerate -m "add document reference_url"
```

Nell'ambiente Docker di questo progetto è stato eseguito:

```sh
docker compose -f docker-compose.dev.yml exec -T backend alembic revision --autogenerate -m "add document reference_url" --rev-id b7e2f6c8d901
```

L'autogenerazione ha rilevato soltanto l'aggiunta di `documents.reference_url`. Lo script generato è stato poi integrato con il backfill dei link legacy e dei metadati vettoriali: Alembic non genera automaticamente le migrazioni dei dati. Per riprodurre la generazione, usare una copia del repository senza questa revisione e un database di prova alla revisione padre, evitando revisioni duplicate.

## Script completo incluso nel repository

File: `alembic/versions/b7e2f6c8d901_add_document_reference_url.py`.

```python
"""add document reference_url

Revision ID: b7e2f6c8d901
Revises: a3c9d2f4b7e1
Create Date: 2026-10-14 20:59:25.517194

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7e2f6c8d901'
down_revision = 'a3c9d2f4b7e1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('documents', sa.Column('reference_url', sa.String(length=2048), nullable=True))
    # Preserve citation links supplied by legacy clients.
    op.execute("UPDATE documents SET reference_url = link WHERE link ~* '^https?://[^[:space:]]+$'")
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT to_regclass('public.langchain_pg_embedding') IS NOT NULL")).scalar():
        op.execute("""
            UPDATE langchain_pg_embedding e
            SET cmetadata = COALESCE(e.cmetadata, '{}'::jsonb) || jsonb_build_object(
                'reference_url', d.reference_url, 'source_name', d.filename
            )
            FROM documents d
            WHERE e.cmetadata->>'document_id' = d.id::text
        """)


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT to_regclass('public.langchain_pg_embedding') IS NOT NULL")).scalar():
        op.execute("UPDATE langchain_pg_embedding SET cmetadata = cmetadata - 'reference_url' - 'source_name'")
    op.drop_column('documents', 'reference_url')
```

## Applicazione in sviluppo

```sh
docker compose -f docker-compose.dev.yml exec -T backend alembic upgrade head
docker compose -f docker-compose.dev.yml exec -T backend alembic current
docker compose -f docker-compose.dev.yml exec -T backend alembic check
docker compose -f docker-compose.dev.yml exec -T frontend npm run generate-api:docker
docker compose -f docker-compose.dev.yml up -d --no-deps frontend
docker compose -f docker-compose.dev.yml restart worker beat
```

Il backend in sviluppo ricarica il codice automaticamente. Worker e scheduler vanno riavviati perché Celery non ricarica automaticamente le funzioni. Il frontend usa un proxy per `/api` e `/static`: in Docker `API_PROXY_TARGET=http://backend:8000`; fuori Docker il valore predefinito è `http://localhost:8000`.

## Applicazione in produzione

La produzione non monta il codice locale: serve ricostruire le immagini. Con database e Redis già attivi, secrets configurati e backup verificato:

```sh
docker compose -f docker-compose.prod.yml build backend worker beat frontend
docker compose -f docker-compose.prod.yml run --rm --no-deps backend alembic current
docker compose -f docker-compose.prod.yml run --rm --no-deps backend alembic upgrade head
docker compose -f docker-compose.prod.yml run --rm --no-deps backend alembic check
docker compose -f docker-compose.prod.yml up -d --no-deps backend worker beat frontend
```

Usare l'utenza e il nome database definiti nei secrets per gli eventuali comandi SQL/backup; i valori di sviluppo non sono credenziali di produzione. La migrazione della colonna è compatibile con il vecchio codice: applicarla prima del rollout del nuovo codice. I comandi di produzione sono documentati, non sono stati eseguiti durante questo intervento.

## Verifiche dopo la migrazione

```sh
docker compose -f docker-compose.dev.yml exec -T db psql -U postgres -d unical_support -c "SELECT version_num FROM alembic_version;"
docker compose -f docker-compose.dev.yml exec -T db psql -U postgres -d unical_support -c "SELECT column_name, data_type, is_nullable, character_maximum_length FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'documents' AND column_name = 'reference_url';"
docker compose -f docker-compose.dev.yml exec -T db psql -U postgres -d unical_support -c "SELECT count(*) AS documents_after, count(reference_url) AS documents_with_public_link FROM documents;"
docker compose -f docker-compose.dev.yml exec -T db psql -U postgres -d unical_support -c "SELECT count(*) AS legacy_links_not_copied FROM documents WHERE link ~* '^https?://[^[:space:]]+$' AND reference_url IS DISTINCT FROM link;"
docker compose -f docker-compose.dev.yml exec -T db psql -U postgres -d unical_support -c "SELECT count(*) AS chunks_with_reference_metadata FROM langchain_pg_embedding WHERE cmetadata ? 'reference_url';"
docker compose -f docker-compose.dev.yml exec -T backend alembic check
```

Atteso: revisione `b7e2f6c8d901`, colonna nullable lunga 2048, numero di documenti invariato, zero link legacy non copiati subito dopo la migrazione, nessuna nuova operazione proposta da `alembic check`. La query sui chunk va eseguita solo se la tabella vettoriale esiste.

Verifica funzionale: caricare un documento con link pubblico, verificarlo nella risposta API e nei metadati dei chunk, quindi controllare che una bozza pertinente includa il nome della fonte e l'URL. Ripetere senza link e verificare che non venga inventato alcun URL. Il recupero di nuove email termina quando sono acquisite e accodate; la generazione delle bozze prosegue in background.

## Rollback

Comando CLI standard:

```sh
alembic downgrade -1
```

In sviluppo, quando la revisione corrente è esattamente `b7e2f6c8d901`:

```sh
docker compose -f docker-compose.dev.yml stop backend worker beat
docker compose -f docker-compose.dev.yml run --rm --no-deps backend alembic downgrade -1
docker compose -f docker-compose.dev.yml run --rm --no-deps backend alembic current
```

Prima di riavviare, ripristinare il codice precedente alla modifica (o un'immagine compatibile). Il nuovo ORM richiede la colonna e non può funzionare dopo averla rimossa. Se esistono revisioni successive, verificare `history` e scegliere consapevolmente la revisione destinazione; `-1` annulla soltanto l'ultima revisione effettiva.

Il downgrade rimuove `reference_url` dalla tabella e `reference_url`/`source_name` dai metadati; conserva documenti, contenuto dei chunk, categorie e `link` legacy. I nuovi URL forniti esclusivamente in `reference_url` vengono persi: esportarli o fare backup prima del rollback. I dati non sono recuperabili con un semplice nuovo upgrade se non erano anche nel campo `link`.

Il rollback è stato verificato su database temporanei con documenti legacy e chunk, e su un database senza tabelle vettoriali. Non è stato eseguito sul database attivo.

Per un ripristino completo, dopo aver fermato gli scrittori, ripristinare il dump in un database vuoto dedicato e collegare una versione del codice compatibile con lo schema contenuto nel dump:

```sh
pg_restore --no-owner --dbname=DATABASE_DESTINAZIONE /percorso/backup.dump
```

## Configurazione lingua e disclaimer

Variabili opzionali, con valori JSON per i dizionari:

```dotenv
AI_RESPONSE_FALLBACK_LANGUAGE=it
AI_RESPONSE_LANGUAGE_OVERRIDES={}
AI_DISCLAIMER_TRANSLATIONS={}
```

Per esempio `AI_RESPONSE_LANGUAGE_OVERRIDES={"es":"en"}` richiede risposte inglesi alle email spagnole. `AI_DISCLAIMER_TRANSLATIONS={"en":"Your approved AI notice."}` sostituisce il testo inglese. Nel comportamento predefinito l'agente risponde nella lingua rilevata; il sistema aggiunge il disclaimer prima del saluto. Sono incluse traduzioni it/en/es/fr/de/pt. Per altre lingue il tool richiede al modello il disclaimer tradotto; non salva una bozza senza disclaimer. Il fallback serve per una lingua ambigua o per chiamate legacy al tool senza codice lingua. Non viene dichiarata una garanzia deterministica sul rilevamento della lingua o sulla qualità della traduzione del modello.

Le variabili possono essere inserite nel `.env` montato in sviluppo; in produzione vanno rese disponibili ai container interessati. Riavviare backend e worker dopo variazioni delle impostazioni d'ambiente. Il testo dei prompt viene invece letto a ogni elaborazione.

## Verifiche automatiche

```sh
docker compose -f docker-compose.dev.yml exec -T worker python -m unittest discover -s tests -v
docker compose -f docker-compose.dev.yml exec -T frontend npm run build
```

I test di migrazione creano database temporanei con prefisso `unical_migration_test_` e li eliminano al termine; richiedono un'utenza con permesso CREATE DATABASE. I test Redis usano chiavi isolate con prefisso `test:gmail-poll:` e non cancellano quelle applicative. Gmail e chiamate LLM sono simulate nei test automatici: nessuna email di prova viene inviata.

Il poller manuale usa `POST /api/emails/fetch-now` (202) e `GET /api/emails/fetch-status/{job_id}`, entrambi autenticati. Il lock Redis copre sia attesa in coda sia esecuzione; richieste ripetute seguono il job esistente. Il lease viene rinnovato all'avvio, scade dopo 660 secondi e supera il limite hard Celery di 600 secondi (soft 540). Gli stati sono conservati per 24 ore. Una terminazione forzata viene segnalata come scaduta alla scadenza del lock; un job vecchio non può cancellare il lock di uno nuovo.

In questo ambiente Gmail segnala `invalid_client`: per un test reale occorre ripristinare credenziali/token OAuth validi tramite la procedura Gmail prevista dal progetto. Non sono stati modificati i file delle credenziali. La compilazione Angular segnala il budget iniziale superato e il formato CommonJS di html2canvas; non impediscono la build.

### Test frontend in un ambiente senza Chrome installato

Il runner può usare il browser integrato già disponibile, con le dipendenze del container:

```sh
docker compose -f docker-compose.dev.yml run --rm --no-deps -p 9876:9876 frontend npm run test -- --watch=false --karma-config=karma.conf.cjs
```

Aprire `http://localhost:9876` nel browser e attendere il risultato. Il container temporaneo termina al completamento. Con Chrome installato si può invece aggiungere `--browsers=ChromeHeadless` al comando; nei container Linux occorre fornire un browser adatto, non incluso nell'immagine frontend attuale.

Verifica nel browser completata: accesso tramite il proxy Docker, pulsante disabilitato durante il controllo, job ricevuto dal worker, errore OAuth riportato all'operatore, navigazione italiana e rifiuto di URL FTP prima di qualsiasi caricamento. Cinque test Angular superati; l'utente temporaneo utilizzato per la verifica è stato rimosso. Nessuna email inviata e nessun documento di prova caricato attraverso la UI.

Esito finale: 25 test backend e 5 test Angular superati, build di produzione completata e `alembic check` senza differenze. Il file locale `celerybeat-schedule` è uno stato runtime già tracciato nel repository e viene aggiornato automaticamente dal servizio Beat durante l’esecuzione; non contiene una modifica al codice applicativo. La modifica al Dockerfile già presente prima dell’intervento è stata preservata.

## Verifica dopo aggiornamento OAuth (14 ottobre 2026)

Il precedente blocco OAuth è risolto: accesso Gmail e lettura dei messaggi riusciti. Il poller automatico ha acquisito due email; entrambe sono state classificate ed elaborate fino a `ESCALATED`. Al momento della verifica la tassonomia e la base documentale erano vuote: l'intervento umano è quindi coerente con la mancanza di fonti utilizzabili. Le chiamate Groq, Gemini ed embedding risultano riuscite.

Il controllo manuale ha terminato con stato `completed` e zero nuove email non lette. Non sono state inviate risposte.

È stata eseguita anche una prova reale con documento sintetico in una raccolta vettoriale isolata: embedding, retrieval, reranking e risponditore hanno funzionato. Tre casi (italiano, inglese, spagnolo) hanno prodotto la lingua attesa, disclaimer iniziale, dato recuperato corretto e URL della fonte. La raccolta è stata eliminata nel blocco `finally`; nessun documento o email di collaudo è stato inserito nelle tabelle applicative. Questa prova non modifica le due email acquisite.

Prova ripetibile, facoltativa, con chiamate reali ai provider AI:

```sh
docker compose -f docker-compose.dev.yml exec -T worker python tests/smoke_ai_live.py
```

L'utente UI della verifica precedente (`codex-ui-test@example.com`) era temporaneo ed è stato eliminato. Per creare un account personale usando lo script interattivo, dalla radice del progetto:

```sh
docker compose -f docker-compose.dev.yml exec backend python create_user.py
```

Non usare `-T`: il terminale interattivo serve per l'inserimento nascosto della password. Inserire una email valida, una password di almeno 8 caratteri con conferma e scegliere `1` per admin oppure `2` per user. Accedere poi a `http://localhost:4200` con le credenziali scelte. Il ruolo admin permette anche di modificare la configurazione dei modelli AI.

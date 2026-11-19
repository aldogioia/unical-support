# DEPLOY

Procedura manuale tramite SSH, su root, Git e Docker Compose. Gli script di deploy automatico sono stati rimossi.

## Ambiente confermato

- SSH: `UnicalSupport`, attraverso `UnicalSupportJump`.
- Progetto: `/home/operatore/unical_support`.
- Secret: `/home/operatore/secrets`.
- Progetto Compose: `unical_support`.
- Provider attivo: SMTP, con `docker-compose.prod.yml` e `docker-compose.smtp.yml`.
- Volumi: `unical_support_postgres_data`, `unical_support_shared_uploads`, `unical_support_celerybeat_data`.
- Docker richiede root; sul server usare `su`, non sudo.

I tentativi automatici si sono fermati prima di build, arresto dei servizi o migrazioni. Il database non è stato sostituito.

## 1. Accesso e aggiornamento del codice

Dal Mac:

```bash
ssh UnicalSupport
```

Sul server, inserire la password di root quando richiesta:

```bash
su -
cd /home/operatore/unical_support
git status --short
git branch --show-current
```

Verificare checkout, branch e assenza di modifiche locali da preservare. Il pull va eseguito con l'utenza che normalmente gestisce il repository e dispone dell'accesso Git.

```bash
git pull --ff-only
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml config --quiet
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml ps
```

Conservare entrambi i file Compose e lo stesso nome progetto per tutti i comandi. `.env` e secret restano sul server, fuori da Git.

## 2. Build delle immagini applicative

```bash
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml build backend worker beat frontend
```

Le modifiche del 18 novembre aggiungono la dipendenza Python Langfuse, il salvataggio delle fonti e il relativo pannello; rimuovono il badge AI Confidence. Ricostruire le immagini Python e Angular con la cache normale: Docker aggiorna lo strato delle dipendenze quando necessario. Non serve `--no-cache`. Il solo restart non carica il nuovo codice nelle immagini di produzione.

Attendere il completamento della build prima di fermare i servizi. PostgreSQL e Redis non richiedono una ricostruzione né una ricreazione.

## 3. Arresto applicativo e backup

È prevista una finestra di indisponibilità. Fermare gli scrittori, mantenendo database e Redis attivi:

```bash
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml stop --timeout 660 backend worker beat frontend
umask 077
mkdir -p /home/operatore/backups
unical_backup="/home/operatore/backups/unical-support-$(date +%Y%m%d-%H%M%S).dump"
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml exec -T db sh -ec 'export PGPASSWORD="$(cat "$POSTGRES_PASSWORD_FILE")"; exec pg_dump -U "$(cat "$POSTGRES_USER_FILE")" -d "$(cat "$POSTGRES_DB_FILE")" -Fc' > "$unical_backup"
```

Solo se pg_dump termina senza errori, verificarne il catalogo:

```bash
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml exec -T db pg_restore --list < "$unical_backup"
```

Non procedere se il backup o la verifica falliscono. Il dump contiene anche gli embedding PostgreSQL. La lettura del catalogo non sostituisce una prova periodica di restore su un database separato. Conservare una copia protetta fuori macchina.

## 4. Alembic, prima del riavvio

Con i servizi applicativi fermi e il backup verificato:

```bash
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml run --rm --no-deps --no-build -T backend alembic current
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml run --rm --no-deps --no-build -T backend alembic upgrade head
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml run --rm --no-deps --no-build -T backend alembic check
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml run --rm --no-deps --no-build -T backend alembic current
```

Eseguire ogni comando solo se il precedente è riuscito. La head attuale è `c2d8e4f6a901`: aggiunge `emails.retrieved_sources JSONB NULL` senza modificare email, bozze o documenti esistenti. La migrazione è necessaria prima di avviare il nuovo backend/worker, anche se Langfuse rimane disabilitato. `upgrade head` applica anche eventuali revisioni precedenti mancanti: leggerle prima di procedere.

Alembic è un passaggio manuale, non viene eseguito automaticamente all'avvio. Non generare nuove revisioni per distribuire quelle già presenti. Dettagli: [MIGRATIONS](MIGRATIONS.md).

## 5. Avvio e verifica

```bash
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml up -d --no-deps --no-build backend worker frontend
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml exec -T backend celery -A app.core.celery_app inspect ping --timeout 10
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml up -d --no-deps --no-build beat
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml ps
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml logs --tail=100 backend worker beat
```

Avviare Beat dopo che backend e worker risultano disponibili. Verificare login, email e documenti esistenti, revisione documentale e polling. Il tunnel LLM deve essere già attivo quando configurato: questa procedura non lo avvia.

`up` ricrea i container applicativi quando l'immagine è cambiata; i volumi rimangono quelli esistenti. Non usare `down -v` o cancellare volumi per un aggiornamento. Redis non ha persistenza nel Compose corrente: lasciarlo attivo per conservare le code.

## Langfuse interno, attivazione separata

Il normale aggiornamento applica la correzione delle fonti e rimuove il badge; il monitoraggio resta disabilitato finché non viene configurato. Seguire [OBSERVABILITY](OBSERVABILITY.md) per avviare `docker-compose.langfuse.yml` con il progetto separato `unical_langfuse`, creare il progetto e le chiavi, e abilitare il worker.

Dopo l'attivazione aggiungere `-f docker-compose.observability.yml` a tutti i prefissi Compose applicativi riportati sopra. L'overlay monta i secret e imposta l'URL di Langfuse nel worker. Non aggiungere il file dello stack Langfuse al Compose applicativo. I due database hanno volumi e procedure di backup distinti.

## Altri provider e rollback

La procedura descrive SMTP, il provider confermato sul server. Per Gmail API servono credenziali e token persistenti montati separatamente: la build li esclude e non li copia automaticamente dai vecchi container.

Se build o migrazione falliscono, fermarsi e verificare l'errore prima di riavviare. Un ritorno al codice precedente richiede compatibilità con lo schema effettivo. Un downgrade non recupera automaticamente dati eliminati; il restore dal dump è una procedura separata e può perdere gli aggiornamenti successivi al backup.

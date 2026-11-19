# Eliminare tutte le email dal database di produzione

Procedura manuale per il server Unical Support. Svuota `public.emails` e le associazioni in `public.email_category`, compresi bozze, risposte generate e record delle email inviate. Conserva utenti, categorie, documenti, embedding, impostazioni e segnalazioni. Non elimina messaggi dalla casella Gmail/IMAP.

Dopo COMMIT la cancellazione è definitiva nel database operativo; il backup è il riferimento per un eventuale recupero. Non occorrono build o migrazioni Alembic. Eseguire una fase per volta e fermarsi se un comando fallisce. I comandi seguenti sono una guida: non sono stati eseguiti sulla produzione.

## 1. Collegarsi e fermare gli scrittori

Dal Mac:

```bash
ssh UnicalSupport
```

Sul server, usare la password di root per su:

```bash
su -
cd /home/operatore/unical_support
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml stop --timeout 660 beat backend worker
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml ps -a
```

Prima di proseguire verificare che beat, backend e worker siano fermi e db sia attivo. Lasciare PostgreSQL e Redis in esecuzione. L'interfaccia può risultare temporaneamente non disponibile mentre il backend è fermo. Evitare altri interventi o scritture dirette sul database durante questa manutenzione.

## 2. Salvare e verificare un backup

Nella stessa sessione root:

```bash
umask 077
mkdir -p /home/operatore/backups
unical_email_backup="/home/operatore/backups/prima-pulizia-email-$(date +%Y%m%d-%H%M%S).dump"
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml exec -T db sh -ec 'export PGPASSWORD="$(cat "$POSTGRES_PASSWORD_FILE")"; exec pg_dump -U "$(cat "$POSTGRES_USER_FILE")" -d "$(cat "$POSTGRES_DB_FILE")" -Fc' > "$unical_email_backup"
```

Solo se pg_dump termina senza errori:

```bash
ls -lh "$unical_email_backup"
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml exec -T db pg_restore --list < "$unical_email_backup"
```

Annotare il percorso del file. Se il dump è vuoto o pg_restore segnala errori, non procedere alla cancellazione. Si tratta di un backup completo del database, inclusi i vettori; la verifica del catalogo non è una prova completa di restore. Per un recupero, ripristinare prima su un database separato e valutare quali dati recuperare, senza sovrascrivere automaticamente gli altri dati operativi.

## 3. Aprire PostgreSQL

```bash
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml exec db sh -ec 'export PGPASSWORD="$(cat "$POSTGRES_PASSWORD_FILE")"; exec psql -X -v ON_ERROR_STOP=1 -U "$(cat "$POSTGRES_USER_FILE")" -d "$(cat "$POSTGRES_DB_FILE")"'
```

Il comando legge utente, password e nome database dai secret del container, senza stamparli. Da questo momento i comandi sono SQL nel prompt psql, non comandi della shell Linux.

## 4. Cancellare in una transazione e controllare il risultato

Nel prompt psql:

```sql
BEGIN;

SELECT status, count(*) AS numero_email
FROM public.emails
GROUP BY status
ORDER BY status;

DELETE FROM public.email_category;
DELETE FROM public.emails;

SELECT count(*) AS email_rimaste FROM public.emails;
SELECT count(*) AS associazioni_rimaste FROM public.email_category;
```

Gli ultimi due conteggi devono essere zero. Le associazioni vengono eliminate esplicitamente per non dipendere da cancellazioni automatiche o da TRUNCATE CASCADE su altre tabelle. Se emergono tabelle o vincoli imprevisti, non aggirarli con CASCADE: fermarsi e verificarli.

Solo se il risultato è quello desiderato, confermare:

```sql
COMMIT;
```

Invece, per annullare prima del COMMIT, oppure dopo qualsiasi errore SQL:

```sql
ROLLBACK;
```

COMMIT e ROLLBACK sono alternative, non due passi consecutivi. Dopo COMMIT, ROLLBACK non recupera le righe eliminate.

Uscire da psql:

```text
\q
```

## 5. Riavviare e decidere quando riprendere il polling

Nella shell root:

```bash
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml start backend
```

Ricaricare il Review Hub e verificare l'elenco vuoto prima di riattivare l'elaborazione. Quando si vuole riprendere la normale acquisizione:

```bash
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml start worker beat
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml ps
```

Il polling legge i messaggi non letti. La cancellazione rimuove anche gli identificativi usati per riconoscere le email già importate: vecchi messaggi ancora non letti o riportati a non letti potranno quindi essere importati di nuovo. Anche un job di polling già in coda può ripartire appena si avvia il worker. Se si vuole escludere quei messaggi, gestirne lo stato di lettura nella casella prima di riattivare worker e Beat.

Nel codice corrente i task di classificazione/risposta relativi a UUID eliminati vengono ignorati; non occorre svuotare Redis per questa operazione. Svuotarlo potrebbe perdere anche lavori documentali ancora in coda.

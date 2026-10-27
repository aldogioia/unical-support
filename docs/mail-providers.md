# Provider email intercambiabili

`EmailClient` è la classe astratta per lettura dei non letti, marcatura come
letti e invio delle risposte. `get_email_client()` seleziona il provider con
`MAIL_PROVIDER=gmail_api` (predefinito) oppure `MAIL_PROVIDER=smtp`.
La selezione vale sia per il polling del worker sia per l'invio dal backend.
`smtp` legge via IMAP e invia via SMTP; entrambi i protocolli usano TLS e
autenticazione con username/password. Non servono nuove dipendenze Python.

## Gmail e password per app

Per Gmail usare l'indirizzo completo e una **password per app**, creata con
verifica in due passaggi attiva, se consentita dall'organizzazione.
La normale password Google non sostituisce OAuth in questo flusso.
Le password per app non sono soggette alla scadenza settimanale dei refresh
token OAuth di un'app in testing, ma possono essere revocate (anche dopo
la modifica della password dell'account).

Riferimento: https://support.google.com/accounts/answer/185833?hl=it

Per altri provider verificare che siano consentiti login IMAP/SMTP con
password o password per app. I parametri host, porta e TLS sono configurabili.
Sono supportati TLS implicito (`ssl`) e upgrade obbligatorio (`starttls`);
non è previsto l'invio di credenziali su connessioni in chiaro.

## Sviluppo

Aggiungere a `.env` le impostazioni di `.env.mail.example`, impostando
`MAIL_PROVIDER=smtp`, `MAIL_USERNAME` e `MAIL_PASSWORD` (senza spazi aggiunti
alla password per app). Il file non va committato. Con i valori predefiniti:

```dotenv
MAIL_PROVIDER=smtp
MAIL_USERNAME=support@example.org
MAIL_PASSWORD=your-app-password
MAIL_IMAP_HOST=imap.gmail.com
MAIL_IMAP_PORT=993
MAIL_SMTP_HOST=smtp.gmail.com
MAIL_SMTP_PORT=465
MAIL_SMTP_SECURITY=ssl
```

Per SMTP con STARTTLS impostare `MAIL_SMTP_PORT=587` e
`MAIL_SMTP_SECURITY=starttls`. Per IMAP con STARTTLS usare la porta indicata
dal provider (normalmente 143) e `MAIL_IMAP_SECURITY=starttls`.

```bash
docker compose -f docker-compose.dev.yml restart backend worker
```

## Produzione

Aggiornare il codice sul server. Inserire in `.env` le impostazioni non
segrete di `.env.mail.example`, almeno `MAIL_USERNAME`. Copiare la password
nel file `/home/operatore/secrets/mail_password`, senza aggiungerla a `.env`,
con permessi coerenti con gli altri secret. Se il file si trova altrove,
impostare `MAIL_PASSWORD_SECRET_FILE`. Il valore viene letto tramite
`/run/secrets/mail_password` da Pydantic, senza inserirlo nel Compose.

Usare l'overlay per abilitare il provider e montare la password in entrambi
i servizi. Non modifica reti, tunnel LLM, database o Redis:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.smtp.yml config --quiet
docker compose -f docker-compose.prod.yml -f docker-compose.smtp.yml build backend worker
docker compose -f docker-compose.prod.yml -f docker-compose.smtp.yml up -d --no-deps backend worker
docker compose -f docker-compose.prod.yml -f docker-compose.smtp.yml logs --tail=100 -f backend worker
```

Usare entrambi i file anche per i successivi aggiornamenti. Beat continua
ad accodare lo stesso task; è il worker a scegliere il provider. Per tornare
a Gmail API ricreare backend e worker con il solo Compose di produzione e
assicurarsi che abbiano un token valido.

Il provider Gmail non avvia più un browser dai processi applicativi quando
il token manca: restituisce un errore. Il consenso interattivo rimane nel
comando `python -m app.listener.gmail_client --reauth`.

## Identificativi e risposte

Il campo esistente `gmail_id` contiene l'identificativo del trasporto e non
richiede migrazioni. Gmail IMAP usa `X-GM-MSGID`, convertito nel formato
esadecimale delle Gmail API: sulla stessa casella il passaggio tra i due
provider conserva gli identificativi e permette risposte ai messaggi già
importati. Riferimento: https://developers.google.com/workspace/gmail/imap/imap-extensions

Per server IMAP generici l'identificativo include casella, cartella,
UIDVALIDITY e UID: evita collisioni e non dipende dai numeri di sequenza.
Se si cambia casella/cartella o il server cambia UIDVALIDITY, i precedenti
identificativi non sono riutilizzabili automaticamente.

Il client usa `BODY.PEEK` e segna un messaggio come letto solo dopo
l'acquisizione. Non esegue EXPUNGE. Legge al massimo `MAIL_FETCH_LIMIT`
messaggi per controllo (predefinito 50) e usa un timeout per operazione
`MAIL_TIMEOUT_SECONDS` (predefinito 30). Per ogni risposta recupera gli
header del messaggio originale nella cartella configurata (predefinita
`INBOX`): il messaggio deve quindi essere ancora presente. Per Gmail,
se occorre rispondere anche ad archiviati, si può configurare la cartella
IMAP "Tutti i messaggi" usando il nome effettivo esposto dal server.

Le risposte mantengono Message-ID/References dell'originale, testo, HTML,
nota multilingua e logo inline. SMTP non fornisce il `threadId` Gmail:
l'accorpamento finale dei thread dipende dal client destinatario.
Per provider generici non viene aggiunta automaticamente una copia nella
cartella Inviati; Gmail gestisce le proprie copie degli invii SMTP.

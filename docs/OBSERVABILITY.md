# Token LLM e fonti consultate

Aggiornamento del 18 novembre 2026. L'integrazione è implementata e collaudata localmente; lo stack Langfuse interno e le relative chiavi progetto devono ancora essere predisposti sul server. Il tracciamento applicativo è disabilitato per default.

## Cosa viene misurato

`app/core/llm_observability.py` collega i callback LangChain dei modelli a generazioni Langfuse. Copre classificazione email, generazione della risposta, tutti i tentativi del fallback senza tool calling e normalizzazione Markdown dei documenti. Le chiamate nello stesso tentativo hanno un trace ID comune; entity_id identifica email/documento, stage la fase e provider/model il modello richiesto.

Vengono esportati solo identificativi interni, modello, fase, tempi, tipo dell'eventuale errore e usage restituito dal provider. Non vengono esportati mittente, oggetto, corpo, prompt, contenuto dei tool, frammenti o risposta generata. La callback non riceve istruzioni dal modello per decidere il conteggio.

I token di input, output e totale provengono da usage_metadata normalizzato o dai conteggi del provider. I dati duplicati fra messaggio e llm_output non vengono sommati. I token letti dalla cache sono separati dall'input ordinario per evitare doppio conteggio. Assenza di usage è un dato mancante, non zero: per i modelli locali il server deve restituire usage nell'API compatibile OpenAI. Gli embedding non espongono usage tramite l'interfaccia LangChain usata dal progetto e non sono inclusi in questo conteggio.

Langfuse può calcolare i costi quando riconosce il modello e dispone di prezzi corretti. Per modelli locali/alias impostare i prezzi nel progetto Langfuse; un costo assente non equivale a costo zero. I conteggi del provider non sono un limite di spesa: questa modifica non blocca le richieste oltre una soglia.

L'SDK viene inizializzato solo se abilitato e dopo il fork del worker. Indisponibilità di Langfuse o chiavi mancanti non interrompono la generazione. L'export è asincrono; la chiusura ordinata dei processi worker tenta il flush. Un'interruzione forzata o un collector indisponibile può perdere eventi: per fatturazione definitiva confrontare anche i dati del provider.

Riferimenti ufficiali: [SDK Python](https://python.reference.langfuse.com/langfuse), [token e costi](https://langfuse.com/docs/observability/features/token-and-cost-tracking). Il progetto usa SDK Python 4.x; la generazione viene creata con l'API pubblica start_observation, mentre il callback seleziona esclusivamente i dati di consumo.

## Predisporre Langfuse interno

`docker-compose.langfuse.yml` è uno stack **separato**, con web, worker Langfuse, PostgreSQL 17, ClickHouse, Redis persistente e storage S3 MinIO. Usare sempre il progetto `unical_langfuse`: non aggiungere questo file al Compose applicativo `unical_support`. I volumi e la rete restano separati; nessuna tabella Langfuse viene aggiunta al database della piattaforma.

Il solo worker Celery applicativo riceve il collegamento al monitoraggio tramite l'overlay. I sei servizi dello stack Langfuse sono l'infrastruttura che riceve, elabora e conserva gli eventi: non rappresentano sei servizi applicativi strumentati. Il worker Langfuse elabora la telemetria; il worker Unical Support esegue le chiamate AI.

La porta web è pubblicata soltanto su 127.0.0.1:3000; i database e lo storage non hanno porte host. Il Compose è adattato dal [file ufficiale](https://github.com/langfuse/langfuse/blob/main/docker-compose.yml). La [guida ufficiale alla VM](https://langfuse.com/self-hosting/deployment/docker-compose) raccomanda almeno 4 core, 16 GiB RAM e spazio adeguato (indicativamente 100 GiB): verificare la capacità prima di aggiungere lo stack alla VPS applicativa, oppure usare una macchina interna dedicata.

Sul server, nella cartella del progetto e con l'accesso root abituale:

```bash
su -
cd /home/operatore/unical_support
cp .env.langfuse.example /home/operatore/secrets/langfuse.env
chmod 600 /home/operatore/secrets/langfuse.env
```

Compilare il file copiato. Per ognuna delle sette variabili LF_* vuote generare **un valore diverso** con `openssl rand -hex 32`; la chiave di cifratura deve avere 64 caratteri hex. Usare valori hex anche per la password PostgreSQL per evitare problemi di escaping nell'URL. Conservare password, salt e chiave di cifratura: non rigenerarli a ogni riavvio. LF_IMAGE_TAG=4 segue il major ufficiale; prima del rollout operativo fissare il tag/digest della release 4 scelta per web e worker. LF_MINIO_IMAGE permette analogamente di fissare l'immagine storage.

```bash
docker compose -p unical_langfuse --env-file /home/operatore/secrets/langfuse.env -f /home/operatore/unical_support/docker-compose.langfuse.yml config --quiet
docker compose -p unical_langfuse --env-file /home/operatore/secrets/langfuse.env -f /home/operatore/unical_support/docker-compose.langfuse.yml up -d
docker compose -p unical_langfuse --env-file /home/operatore/secrets/langfuse.env -f /home/operatore/unical_support/docker-compose.langfuse.yml logs --tail=100 web worker
```

Per le sessioni SSH si può definire una scorciatoia indipendente dalla directory corrente:

```bash
alias lf='docker compose -p unical_langfuse --env-file /home/operatore/secrets/langfuse.env -f /home/operatore/unical_support/docker-compose.langfuse.yml'
lf ps -a
lf logs --tail=60 minio redis
```

L'alias va ridefinito nelle nuove sessioni. Un errore `open /root/docker-compose.langfuse.yml` indica un percorso relativo eseguito dalla directory sbagliata; i percorsi assoluti sopra evitano questo problema. In caso di dipendenze non disponibili leggere i log dei servizi coinvolti: `Created` per web/worker non implica che siano già avviati, e `health: starting` non prova da solo un guasto. Il codice 127 di un processo richiede di identificare l'errore specifico dai log; non attribuirlo automaticamente alla memoria.

### Compatibilità CPU della VM

Sulla VM di produzione il 19 novembre 2026 MinIO ha restituito `Fatal glibc error: CPU does not support x86-64-v2`. Anche l'esecuzione diretta di `/usr/bin/minio --version` e `/usr/bin/mc --version`, senza shell, ha confermato il requisito AMD64 v2. Il problema riguarda le istruzioni CPU esposte alla VM; cambiare entrypoint o aumentare la RAM non lo risolve.

L'amministratore dell'hypervisor deve verificare se il processore fisico supporta x86-64-v2 e scegliere un modello CPU virtuale che esponga tali istruzioni (eventualmente host-passthrough, se appropriato per l'infrastruttura). In alternativa occorre un'immagine S3 compatibile con la CPU disponibile e verificata per avvio e healthcheck. Le vecchie varianti MinIO cpuv1 su Docker Hub e Quay non sono risultate scaricabili durante questa verifica: non usarne tag non verificati come correzione automatica.

In attesa della modifica si può arrestare soltanto lo stack Langfuse con `lf stop`; configurazione, secret e volumi vengono conservati. Alla ripresa usare `lf up -d`, verificare `lf ps -a` e i log delle dipendenze prima di creare il progetto e abilitare l'overlay applicativo. Il warning Redis su `vm.overcommit_memory` va trattato separatamente: nel log osservato Redis accettava le connessioni e non era il blocco di avvio.

Dal Mac aprire il tunnel, usando il normale jump SSH:

```bash
ssh -N -L 3000:127.0.0.1:3000 UnicalSupport
```

Aprire `http://localhost:3000`, creare il primo utente, organizzazione e progetto. Langfuse non ha un account predefinito. Creare le chiavi API del progetto e salvarle sul server in:

```text
/home/operatore/secrets/langfuse_public_key
/home/operatore/secrets/langfuse_secret_key
```

Proteggere i file con permessi 600. La procedura non crea utenti né credenziali automaticamente. Se Langfuse è su un'altra macchina interna, usare il suo URL HTTPS e predisporre l'accesso di rete; LF_PUBLIC_URL descrive l'indirizzo usato dal browser.

Backup e retention Langfuse sono indipendenti dai backup applicativi: includere PostgreSQL, ClickHouse e storage S3. Non usare down -v per aggiornare lo stack.

## Abilitare il monitoraggio della piattaforma

Aggiungere al `.env` applicativo sul server:

```dotenv
LANGFUSE_ENABLED=true
APP_LANGFUSE_BASE_URL=http://127.0.0.1:3000
LANGFUSE_ENVIRONMENT=production
LANGFUSE_RELEASE=identificativo-del-commit-distribuito
```

Il worker usa la rete host, quindi raggiunge lo stack sulla porta loopback. L'overlay `docker-compose.observability.yml` monta le chiavi come Docker secrets nel solo worker. I percorsi sono configurabili tramite LANGFUSE_PUBLIC_KEY_FILE e LANGFUSE_SECRET_KEY_FILE.

Eseguire prima build e migrazione applicativa secondo [DEPLOY](DEPLOY.md). Dopo avere configurato le chiavi, includere l'overlay quando si ricrea il worker:

```bash
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml -f docker-compose.observability.yml config --quiet
docker compose -p unical_support -f docker-compose.prod.yml -f docker-compose.smtp.yml -f docker-compose.observability.yml up -d --no-deps --no-build worker
```

Mantenere l'overlay anche nei successivi comandi di aggiornamento del worker. Per disabilitare impostare LANGFUSE_ENABLED=false e ricrearlo. La correzione delle fonti e la UI funzionano anche con Langfuse disabilitato.

In sviluppo il worker legge il `.env` montato: usare LANGFUSE_ENABLED, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY e LANGFUSE_BASE_URL direttamente. Su Docker Desktop l'URL verso Langfuse sull'host è `http://host.docker.internal:3000`; riavviare il worker dopo la modifica. Nessuna chiave va inserita nel frontend.

## Perché le fonti non comparivano

Il Review Hub mostrava un blocco statico con “Non disponibili”. Il contratto API non conteneva le fonti: il retrieval le passava al modello, ma i frammenti non venivano conservati con la bozza. Una risposta corretta o un link nel testo non potevano modificare quel pannello.

La revisione Alembic `c2d8e4f6a901` aggiunge `emails.retrieved_sources JSONB NULL`. I tool vincolati all'email raccolgono gli effettivi risultati di ricerca e li salvano nella stessa transazione della bozza/escalation, sotto gli stessi controlli di token, revisione e proprietà manuale. Il percorso di fallback salva lo stesso formato.

Ogni snapshot contiene document_id se disponibile, source_name, reference_url valido o null, pagina e un estratto fino a 2000 caratteri. Le ricerche ripetute non duplicano lo stesso frammento; la raccolta è limitata a 60 frammenti. Il pannello raggruppa per documento e mostra link e passaggi come testo, senza eseguire markup recuperato. I documenti senza URL sono visibili all'operatore con il relativo avviso; le regole sulle citazioni nell'email continuano a richiedere link validi.

NULL indica una bozza senza storico registrato; [] una ricerca registrata senza frammenti utilizzabili. Le bozze storiche non vengono rigenerate né vengono inventate fonti retroattive. Modifiche manuali successive conservano lo snapshot della generazione originale, e il pannello invita a verificarne la coerenza con il testo revisionato.

Il badge AI confidence è stato rimosso da Review Hub, componente condiviso e catalogo Design System. Il campo backend ai_confidence e la colonna esistente restano per compatibilità dei dati/client precedenti; nessun punteggio viene visualizzato all'operatore.

## Collaudo

- 148 test backend superati, con 14 subtest: includono transazioni reali PostgreSQL, upgrade/downgrade e protezione delle bozze.
- SDK Langfuse reale collaudato con ricevitore OTLP locale e dati sintetici: verificati conteggi ed esclusione del testo.
- 90 test Angular superati, inclusi raggruppamento dei frammenti, link, stato storico/ricerca vuota e escaping del contenuto.
- Build Angular riuscita; resta il warning CommonJS preesistente di html2canvas.
- Configurazioni Compose validate: volumi Langfuse separati e osservabilità disabilitata per default nell'overlay.

Non sono stati eseguiti deploy remoti, invii email o chiamate a modelli reali per questi test. La migrazione è stata applicata soltanto a database temporanei di collaudo.

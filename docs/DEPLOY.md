# DEPLOY

## Obiettivo e stato

Lo script `scripts/deploy.py` aggiorna un'installazione Docker Compose **già presente**: si collega tramite SSH jump, carica il codice del workspace in una nuova release, costruisce le immagini sul server e avvia i container applicativi. Include le modifiche locali non ancora committate. Non installa Docker, non inizializza un nuovo database e non trasferisce un dump locale sul server.

Il database esistente deve essere mantenuto. Lo script richiede container PostgreSQL/Redis già attivi, individua il progetto e i volumi effettivi e rifiuta installazioni ambigue. Non esegue `down`, cancellazioni di volumi, `stamp`, restore o ricreazioni di db/redis. Prima di ogni rollout fa un dump verificato; l'aggiornamento dello schema avviene soltanto con `--migrate`.

Stato al 3 novembre 2026: l'accesso SSH con password e i percorsi `/home/operatore/unical_support` e `/home/operatore/secrets` sono confermati. I tentativi di --check hanno rilevato accesso negato al socket Docker e assenza di sudo. Per questo server usare `--interactive-ssh --su`. Non è stato eseguito un deploy remoto durante l'intervento; progetto Docker, volumi e prerequisiti applicativi restano da verificare con --check --su.

## Connessione SSH

Configurazione in `~/.ssh/config`:

```sshconfig
Host UnicalSupportJump
    HostName 160.97.63.29
    User unicalsupport
    Port 60

Host UnicalSupport
    HostName 160.97.104.166
    User operatore
    Port 22
    ProxyJump UnicalSupportJump
```

Per l'accesso con password usare `--interactive-ssh` dal terminale del **Mac**, nella radice del progetto locale. Se si è ancora nella shell remota, uscire prima con `exit`:

```bash
python3 scripts/deploy.py --interactive-ssh \
  --remote-dir /home/operatore/unical_support --check
```

OpenSSH chiede prima la password di `unicalsupport@160.97.63.29`, poi quella di `operatore@160.97.104.166`, salvo autenticazioni già soddisfatte tramite chiave. Le password vengono lette dal terminale da OpenSSH, non dallo script Python. Non passare password come argomenti o file di configurazione. Il timeout di connessione in questa modalità è 180 secondi, per consentire le due autenticazioni.

Lo script apre prima una connessione master con un socket in una directory temporanea privata; controllo, upload ed esecuzione usano la stessa connessione. Alla fine, anche in caso di errore, chiude il proprio master. Ogni nuova invocazione dello script effettua una nuova autenticazione: un --check separato e il successivo deploy possono richiedere entrambi le due password. Non viene mantenuta una sessione del precedente `ssh UnicalSupport`.

Per accessi automatici usare le chiavi già autorizzate per i due account, senza --interactive-ssh. Se l'agent offre troppe chiavi, aggiungere `IdentityFile` e `IdentitiesOnly yes` **a entrambe le sezioni**, oppure usare le opzioni dello script:

```bash
python3 scripts/deploy.py --check \
  --identity ~/.ssh/chiave_server \
  --jump-identity ~/.ssh/chiave_jump
```

I percorsi delle chiavi sono esempi: sostituirli con quelli corretti. Non vengono cambiate automaticamente configurazione SSH, chiavi o permessi sul server. Il default resta non interattivo su entrambi gli host; --interactive-ssh abilita password e passphrase. La verifica delle host key rimane stretta in entrambe le modalità. Al primo accesso verificare le impronte con l'amministratore e completare un normale `ssh UnicalSupport` interattivo; non disabilitare il controllo delle host key.

### Docker richiede root: usare su su questo server

Il server non dispone di sudo. Usare `--su`, senza `--sudo`, dal Mac:

```bash
python3 scripts/deploy.py --interactive-ssh --su \
  --remote-dir /home/operatore/unical_support --check
```

L'accesso SSH resta come operatore attraverso il jump. Il terminale remoto esegue `su --login root --command ...`: alla richiesta di su inserire **la password di root**, non quella di operatore, salvo che coincidano. La password viene letta direttamente da su dal terminale; non passa come argomento, JSON o dato letto da Python. Per un deploy completo su può richiederla due volte, una per l'inventario e una per il rollout; in un --check separato la richiede nuovamente.

L'helper parte nella sessione root, poi usa UID/GID effettivi e gruppi originali di operatore per le operazioni sui file. Soltanto i processi figli che eseguono Docker riprendono l'identità root. In questo modo i file generati di release, runtime e backup restano accessibili a operatore senza chown ricorsivi sul progetto e senza modificare i secret. Questa modalità non dipende da sudo, non cambia i gruppi dell'utente e non cambia i permessi del socket Docker.

I file temporanei dell'inventario restano separati dal terminale di autenticazione e vengono rimossi al termine. `--su` e `--sudo` sono mutuamente esclusivi. Per i comandi manuali del manifest con `docker_access: "su"`, aprire una sessione remota root con `su -` prima di usare Docker; il vettore compose_command in questa modalità non contiene un prefisso sudo.

### Opzione sudo per altri server

Se il controllo restituisce `permission denied ... /var/run/docker.sock`, SSH è riuscito ma l'utente non può accedere direttamente al daemon. Aggiungere `--sudo` sia al controllo sia al deploy:

```bash
python3 scripts/deploy.py --interactive-ssh --sudo \
  --remote-dir /home/operatore/unical_support --check
```

Oltre alle password SSH, può essere richiesta la password sudo di operatore. L'utente deve essere già autorizzato a usare Docker tramite sudo; lo script non modifica sudoers, gruppi o permessi del socket. Python e la creazione di release/backup restano eseguiti come operatore; soltanto Docker viene invocato tramite `sudo -n docker`. Un `sudo -v` nel medesimo terminale verifica o rinnova prima l'autenticazione, anche dopo build lunghe. Le password non vengono raccolte da Python né mescolate con i flussi binari dei backup.

In questa modalità --check carica un piccolo helper in una directory temporanea privata del server, lo esegue con terminale per sudo e legge il risultato JSON da un file separato; poi rimuove i due file e la directory. Non modifica container, schema o dati applicativi. Il solo comando di autenticazione sudo può essere registrato nei log amministrativi. Per i comandi manuali dal manifest con prefisso sudo, eseguire prima `sudo -v` nella propria sessione se la credenziale è scaduta.

## Prerequisiti del server

- Linux, Python 3.9+, Docker Engine e plugin Compose v2 con supporto per `--no-build` e bind `create_host_path: false`.
- L'utente operatore può scrivere nella directory del progetto esistente. Per Docker può usare accesso diretto, su root con --su (questa installazione), oppure sudo con --sudo se disponibile.
- Un solo progetto identificabile, con servizi esistenti `db`, `redis`, `backend`, `worker`, `beat`, `frontend`. In caso di più installazioni specificare `--project`.
- PostgreSQL e Redis già attivi; database e upload su volumi Docker nominati. Bind mount del database o upload divergenti fra backend e worker richiedono una migrazione manuale, non vengono convertiti.
- Spazio sufficiente per build, vecchie immagini, nuova release e dump; accesso del server ai registry Docker e Python/npm.
- Tunnel del modello locale già attivo quando configurato nelle Impostazioni. La procedura non apre il tunnel.

Il Compose produzione legge i secret in `/home/operatore/secrets/`: postgres_user, postgres_password, postgres_db, redis_password, database_url, redis_url, database_url_host, redis_url_host, secret_key, groq_api_key, google_api_key, google_api_key_2 e i tre feedback_email_*. I file devono esistere con valori validi per i servizi utilizzati. Per SMTP serve anche mail_password o il percorso configurato con MAIL_PASSWORD_SECRET_FILE.

Il worker usa la rete host e URL loopback; backend e Beat usano gli host Compose `db` e `redis`. Le porte richieste sono PostgreSQL `127.0.0.1:15432` → 5432 e Redis `127.0.0.1:16379` → 6379. Per derivare i secret del worker senza stampare credenziali:

```bash
python3 scripts/prepare_host_network_secrets.py --secrets-dir /home/operatore/secrets
```

Eseguire sul server con un'utenza autorizzata a leggere/scrivere quei file. Se le porte loopback non sono già esposte, lo script di deploy si ferma: quella modifica richiede una manutenzione separata dei servizi db/redis, con backup e verifica del volume. Redis corrente non è persistente e ricrearlo perde i messaggi in coda. Il deploy applicativo non tenta questa conversione automaticamente.

Frontend Nginx pubblica la porta 80; il Compose non installa TLS né apre il firewall. Dominio, accesso di rete e terminazione HTTPS devono essere predisposti nell'infrastruttura.

## Procedura prevista per il prossimo aggiornamento

Dalla radice del repository:

```bash
# Solo piano locale: nessuna connessione o modifica.
python3 scripts/deploy.py --dry-run --build all --migrate

# Inventario remoto in sola lettura: nessun upload, backup o riavvio.
python3 scripts/deploy.py --interactive-ssh --su --remote-dir /home/operatore/unical_support --check

# Solo se il controllo riesce: rollout completo, con backup e migrazioni.
python3 scripts/deploy.py --interactive-ssh --su --remote-dir /home/operatore/unical_support --build all --migrate
```

`--check` verifica Docker Compose, container, progetto, volumi, provider, directory e porte richieste. Non certifica da solo la validità di tutti i secret, l'autenticazione email o il tunnel LLM. Durante il deploy `compose config --quiet`, i controlli dello schema e le verifiche di avvio aggiungono i rispettivi controlli.

Se il progetto è ambiguo oppure il percorso dei label non è utilizzabile:

```bash
python3 scripts/deploy.py --check --project NOME_ESISTENTE --remote-dir /percorso/esistente
python3 scripts/deploy.py --project NOME_ESISTENTE --remote-dir /percorso/esistente --build all --migrate
```

Usare il nome **esistente** restituito dall'inventario; inventarne uno nuovo non migra i dati. Il percorso indicato deve già esistere.

## Opzioni

| Opzione | Comportamento |
| --- | --- |
| `--build all` | Default: build di backend, worker, beat e frontend sul server |
| `--build backend` | Build di backend, worker e beat; usa l'immagine frontend già presente |
| `--build frontend` | Build del solo frontend; usa le immagini Python già presenti |
| `--build none` | Usa tutte le immagini già disponibili, senza caricare nuove versioni del codice nelle immagini |
| `--no-cache` | Ricostruzione senza cache, incompatibile con build none |
| `--migrate` | Applica le migrazioni incluse con alembic upgrade head dopo il backup |
| `--mail-provider current` | Default: conserva il provider rilevato dal worker |
| `--mail-provider smtp` / `gmail_api` | Cambio esplicito del provider, con i relativi prerequisiti |
| `--overlay /percorso/file.yml` | Mantiene un override aggiuntivo già sul server; ripetibile |
| `--host`, `--jump-host` | Alias SSH; default UnicalSupport e UnicalSupportJump |
| `--identity`, `--jump-identity` | Identità esplicite per destinazione e jump |
| `--interactive-ssh` | Password/passphrase dal terminale su entrambi gli host; una connessione riutilizzata per l'intera invocazione |
| `--sudo` | Docker remoto tramite sudo; terminale dedicato per eventuali richieste di password |
| `--su` | Accesso root tramite su sul server; password di root nel terminale, senza dipendenza da sudo |

Le opzioni di build parziale riguardano la costruzione delle immagini: il rollout ricrea comunque i quattro servizi applicativi, per mantenere riferimenti di rete e runtime coerenti. Usare frontend/none solo quando le immagini Python installate contengono già il codice necessario. Lo script confronta le revisioni Alembic dell'immagine backend con quelle caricate e si ferma se non coincidono; non è una verifica completa dell'identità di tutto il codice. Per distribuire tutte le modifiche correnti usare all.

Senza `--migrate`, uno schema non allineato alla release blocca il deploy prima dell'arresto applicativo. Non viene creato un file Alembic nuovo sul server. Gli overlay personalizzati esistenti vengono segnalati e devono essere esplicitamente mantenuti: non vengono scartati in silenzio. L'overlay SMTP incluso viene invece selezionato automaticamente quando il provider corrente è smtp. `.env` remoto viene usato per l'interpolazione Compose; altre impostazioni runtime vanno dichiarate negli environment/secret degli overlay, non si presume che il file venga copiato nell'immagine.

## Cosa fa il rollout

1. Rileva l'installazione e carica solo codice/build context in `<remote-dir>/.deploy/releases/<id>`. Esclude `.env`, OAuth locali, chiavi, secrets, upload, dump, dipendenze generate e symlink. Non sovrascrive la cartella sorgente precedente.
2. Rilegge l'inventario dopo l'upload e acquisisce un lock per evitare deploy simultanei.
3. Genera `deploy.override.json`: nomi reali di postgres_data e shared_uploads come volumi esterni, stato Beat persistente, build context della nuova release e bind dei file OAuth remoti quando necessari.
4. Valida Compose, conserva le vecchie immagini con tag rollback, costruisce le immagini selezionate e controlla revisioni del codice e schema. I problemi in questa fase lasciano attive le applicazioni precedenti.
5. Ferma backend, worker, beat e frontend con arresto controllato, fino a 660 secondi. PostgreSQL e Redis restano attivi. È prevista un'interruzione applicativa; non è un rollout senza downtime. Evitare scrittori esterni durante la finestra.
6. Salva un dump custom in `.deploy/backups/`, con permessi 600, e ne controlla il catalogo tramite pg_restore. Se fallisce, non migra e non avvia la release.
7. Conserva le credenziali OAuth del server e il token aggiornato dai vecchi container, poi applica eventualmente Alembic e verifica current/check.
8. Ricrea backend, worker e frontend con `--no-deps --no-build`; controlla HTTP del backend e frontend, connessione DB/Redis e ping del worker specifico. Avvia Beat soltanto dopo questi controlli e mostra lo stato.
9. Salva `manifest.json`, con volumi, immagini precedenti, schema precedente/atteso, backup, comando Compose e risultato. Non contiene password o token.

I backup e le release non vengono eliminati automaticamente. Lo script non scarica un backup sul computer locale e non invia email di prova. Con Beat riavviato riprende il normale polling della casella.

## Verifiche successive

Aprire l'indirizzo dell'applicazione sulla rete autorizzata; verificare login, elenco email, documento esistente e pannello di revisione. Controllare log di worker/Beat, polling ogni due minuti, assenza di errori di connessione e risposta del modello se si usa un tunnel. Effettuare un invio solo su una casella di prova autorizzata.

Per i comandi manuali usare il vettore `compose_command` nel manifest. Esempio sul server per mostrare lo stato senza ricostruire il prefisso a mano:

```bash
python3 - /percorso/release/manifest.json <<'PY'
import json, subprocess, sys
manifest = json.load(open(sys.argv[1]))
subprocess.run(manifest['compose_command'] + ['ps'], check=True)
PY
```

Per i log sostituire `['ps']` con `['logs', '--tail=100', 'worker', 'beat']`. Non usare il solo Compose della vecchia cartella per aggiornamenti successivi: si perderebbero override dei volumi, runtime OAuth o provider. I deploy successivi vanno eseguiti nuovamente tramite lo script.

## Interruzione e rollback

Un errore dopo l'arresto ferma anche eventuali nuovi container applicativi; db/redis restano attivi. Il manifest indica se il dump è stato verificato. Non viene eseguito un downgrade automatico, perché una migrazione può eliminare colonne/tabelle e il vecchio codice può essere incompatibile con lo schema già aggiornato. Un'interruzione SSH/processo va trattata allo stesso modo: prima leggere stato e manifest, senza avviare alla cieca vecchie immagini.

Se lo schema è ancora quello precedente, ripristinare i file Compose precedenti elencati nel manifest e le immagini `previous_images` o i tag `PROGETTO-SERVIZIO:rollback-TIMESTAMP`, mantenendo gli stessi volumi. Un semplice docker start dei container precedenti è possibile soltanto se non sono stati ricreati e lo schema è compatibile.

Se lo schema è avanzato, valutare la migrazione inversa e una versione del codice compatibile secondo [MIGRATIONS](MIGRATIONS.md). Il dump permette il recupero, ma il restore non è incluso nello script: va provato su un database separato e pianificato, perché sovrascriverebbe gli aggiornamenti successivi al backup. Non usare down -v, volume prune o stamp head come rimedio.

## Collaudo dello script

```bash
python3 tests/test_deploy.py
python3 scripts/deploy.py --dry-run --build all --migrate
```

Collaudo locale: 32 test superati. Verificano esclusione dei secret, nomi dei volumi, lock, conservazione OAuth, selezione dei servizi, ordinamento backup/migrazione, rifiuto dello schema incompatibile e blocco del rollout se il backup fallisce. Coprono anche modalità SSH interattiva/non interattiva, riuso del socket, chiusura su errore, terminale su/sudo separato dal JSON e integrità dei flussi binari. I test su controllano quoting del comando, identità dei file e ripristino di root soltanto nei figli Docker, simulando le chiamate ai privilegi senza cambiare realmente l'identità del processo di test. I file OAuth vengono letti come archivio in memoria. Un test usa realmente Compose config senza daemon né container; l'autenticazione root e il collaudo completo sul server non sono stati eseguiti.

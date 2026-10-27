# Worker con tunnel SSH sulla VPS

Il worker usa `network_mode: host` per accedere al tunnel SSH dell'LLM,
anche se il tunnel ascolta solo su `127.0.0.1`. In questa modalità non
dispone del DNS dei servizi Compose `db` e `redis`.

PostgreSQL e Redis pubblicano rispettivamente `127.0.0.1:15432` e
`127.0.0.1:16379` sulla VPS. Il worker legge i nuovi secret
`database_url_host` e `redis_url_host`, montati nei percorsi che il codice
già usa (`/run/secrets/database_url` e `/run/secrets/redis_url`).
Backend e beat usano la rete Compose e gli URL originali con `db` e `redis`.
Beat invia i task al broker; le chiamate all'LLM vengono eseguite dal worker.

## Applicazione sul server

Copiare il Compose aggiornato e `scripts/prepare_host_network_secrets.py`
sul server. Dalla cartella del progetto, generare i due nuovi secret:

```bash
sudo python3 scripts/prepare_host_network_secrets.py
docker compose -f docker-compose.prod.yml config --quiet
```

Lo script conserva credenziali, schema, percorso e query degli URL originali,
sostituendo solo host e porta. Non modifica i secret originali e non stampa
le credenziali. Se cambiano gli originali, eseguire nuovamente lo script.

Le porte 15432 e 16379 devono essere libere sulla VPS. La ricreazione di
PostgreSQL e Redis causa una breve interruzione; il volume PostgreSQL viene
conservato. Fermare prima i produttori e consumatori dei task:

```bash
docker compose -f docker-compose.prod.yml stop backend worker beat
docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate db redis
```

Attendere che PostgreSQL e Redis siano pronti nei log, quindi:

```bash
docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate worker beat
```

Se il token Gmail rinnovato è stato copiato nella cartella del progetto
sul server, aggiornare il worker appena ricreato e il backend:

```bash
docker compose -f docker-compose.prod.yml cp ./token.json worker:/app/token.json
docker compose -f docker-compose.prod.yml cp ./token.json backend:/app/token.json
docker compose -f docker-compose.prod.yml restart worker
docker compose -f docker-compose.prod.yml start backend
docker compose -f docker-compose.prod.yml logs --tail=100 -f worker beat
```

La copia del token nei container va ripetuta a ogni ricreazione finché non
viene configurata una persistenza dedicata. La directory condivisa degli
upload rimane montata nel worker anche con la rete host.

Verificare la connessione del worker a Redis e la sua disponibilità (`ready`),
l'assenza di errori di connessione PostgreSQL e infine un task che usa l'LLM.
La validazione Compose locale non verifica il tunnel o il firewall della VPS.

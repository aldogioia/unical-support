# MIGRATIONS

## Regole di esecuzione

Alembic è l'unico percorso per aggiornare lo schema. La creazione automatica delle tabelle all'avvio è disabilitata. Non usare `stamp head` per risolvere tabelle mancanti o differenze non analizzate; il comando registrerebbe una versione senza applicare le modifiche.

Il deploy remoto opzionale `--migrate` esegue il backup, ferma gli scrittori e applica `alembic upgrade head` con la nuova immagine backend. Non rimpiazza il database e non importa i dati locali. Nome del progetto e volumi esistenti vengono verificati prima dell'operazione. Vedere [DEPLOY](DEPLOY.md) per l'esecuzione sul server.

## Revisioni incluse

| Revisione | Modifica |
| --- | --- |
| [e199718ba57d](../alembic/versions/e199718ba57d_initial_production_schema.py) | Schema iniziale |
| [a3c9d2f4b7e1](../alembic/versions/a3c9d2f4b7e1_document_multi_category.py) | Documenti con più categorie |
| [b7e2f6c8d901](../alembic/versions/b7e2f6c8d901_add_document_reference_url.py) | reference_url nullable e backfill dei link/metadati |
| [c8f4a1e6d203](../alembic/versions/c8f4a1e6d203_unify_document_source_link.py) | Unico link reference_url, rimozione del campo legacy link |
| [d4a7e2b9f610](../alembic/versions/d4a7e2b9f610_remove_canned_responses.py) | Rimozione template precompilati, metadati di lingua e disclaimer |
| [e6b9f2a1c430](../alembic/versions/e6b9f2a1c430_add_ai_confidence.py) | Confidence nullable con vincolo [0,1] |
| [f3a6c8e1b245](../alembic/versions/f3a6c8e1b245_add_document_processing_status.py) | Stato di elaborazione e note di revisione documenti |
| [a71d9c4e2f60](../alembic/versions/a71d9c4e2f60_email_arrival_and_processing_guards.py) | Date di arrivo, revisioni bozze e prenotazioni AI |

La head prevista nel codice attuale è `a71d9c4e2f60`. Lo stato della VPS non è stato verificato in questa sessione. Il database locale era stato aggiornato alla head dopo backup durante il lavoro precedente.

La rimozione dei template (`d4a7e2b9f610`) elimina le relative tabelle e il tipo enum: il downgrade ricrea lo schema ma **non i contenuti eliminati**. Questa migrazione non elimina email, categorie, documenti o embedding. La conservazione del database durante il deploy significa riutilizzo dello stesso volume e dei dati applicativi; non significa che le migrazioni non possano rimuovere strutture obsolete. Leggere le revisioni ancora da applicare e verificare il backup prima di procedere.

## Pre e post migrazione in sviluppo

```bash
docker compose -f docker-compose.dev.yml exec -T backend alembic current
docker compose -f docker-compose.dev.yml exec -T backend alembic heads
docker compose -f docker-compose.dev.yml exec -T backend alembic history --verbose
docker compose -f docker-compose.dev.yml exec -T db pg_dump -U postgres -d unical_support -Fc > /percorso/protetto/prima-migrazione.dump
docker compose -f docker-compose.dev.yml exec -T db pg_restore --list < /percorso/protetto/prima-migrazione.dump
```

Annotare la revisione corrente e il numero di utenti, email e documenti. Controllare dimensione del dump, spazio libero, disponibilità degli originali e assenza di deploy concorrenti. In ambienti operativi fermare tutti gli scrittori prima di migrare; in produzione lo fa lo script. Un database con tabelle applicative ma senza revisione Alembic richiede un'analisi dello schema prima dell'aggiornamento.

```bash
docker compose -f docker-compose.dev.yml stop backend worker beat
docker compose -f docker-compose.dev.yml run --rm --no-deps backend alembic upgrade head
docker compose -f docker-compose.dev.yml run --rm --no-deps backend alembic current
docker compose -f docker-compose.dev.yml run --rm --no-deps backend alembic check
docker compose -f docker-compose.dev.yml up -d backend worker beat
```

Verificare revisione attesa, conteggi conservati delle entità ancora previste e campi introdotti. Per l'ultima migrazione:

```bash
docker compose -f docker-compose.dev.yml exec -T db psql -U postgres -d unical_support -c 'SELECT count(*) AS emails, count(received_at) AS with_arrival FROM emails;'
docker compose -f docker-compose.dev.yml exec -T db psql -U postgres -d unical_support -c 'SELECT version_num FROM alembic_version;'
```

Provare salvataggio di una bozza, ricerca documentale e lettura delle API. In caso di modifica ai contratti rigenerare il client OpenAPI come descritto in [OPERATIONS](OPERATIONS.md).

## Generazione di nuove revisioni

Dopo modifica dei modelli, su un database di sviluppo allineato alla revisione precedente:

```bash
docker compose -f docker-compose.dev.yml exec -T backend alembic revision --autogenerate -m "describe schema change"
```

Per riprodurre il comando della modifica email su un ramo **senza** la revisione già inclusa:

```bash
alembic revision --autogenerate -m "add email arrival dates and processing guards"
```

Non creare una revisione duplicata per distribuire codice che contiene già gli script. L'autogenerazione non scrive i backfill e può non rilevare tutti i CHECK o gli enum: revisionare sempre upgrade/downgrade. Le tabelle LangChain sono escluse da `alembic/env.py`; non aggiungerne la rimozione automatica.

## Script completo dell'ultima revisione

Il file eseguibile è quello collegato nella tabella; il codice corrente è:

```python
"""Arrival ordering, optimistic drafts and fenced AI processing.

Revision ID: a71d9c4e2f60
Revises: f3a6c8e1b245
"""
from alembic import op
import sqlalchemy as sa

revision = 'a71d9c4e2f60'
down_revision = 'f3a6c8e1b245'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('emails', sa.Column('received_at', sa.DateTime(timezone=True), nullable=True))
    op.execute('UPDATE emails SET received_at = created_at')
    op.alter_column('emails', 'received_at', nullable=False, server_default=sa.func.now())
    op.create_index('ix_emails_received_id', 'emails', ['received_at', 'id'])
    for column in ['draft_revision', 'processing_generation']:
        op.add_column('emails', sa.Column(column, sa.Integer(), nullable=False, server_default='0'))
    op.add_column('emails', sa.Column('manually_edited', sa.Boolean(), nullable=False, server_default=sa.false()))
    # Conservatively protect existing operator-owned answers, including delivery failures.
    op.execute("UPDATE emails SET manually_edited = true WHERE generated_draft IS NOT NULL AND last_updated_by <> 'System'")
    op.add_column('emails', sa.Column('processing_token', sa.String(36), nullable=True))
    op.add_column('emails', sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('emails', sa.Column('failure_stage', sa.String(16), nullable=True))


def downgrade():
    for column in ['failure_stage', 'processing_started_at', 'processing_token', 'manually_edited', 'processing_generation', 'draft_revision']:
        op.drop_column('emails', column)
    op.drop_index('ix_emails_received_id', table_name='emails')
    op.drop_column('emails', 'received_at')
```

Il backfill usa created_at per le email storiche e protegge in modo conservativo le bozze con autore diverso da System. Non cancella email o testo delle bozze. La retrocessione perde i metadati di concorrenza e la data aggiunta.

## Downgrade e ripristino

Il comando generico è:

```bash
alembic downgrade -1
```

Solo se la revisione corrente è proprio quella da annullare, in un ambiente di sviluppo fermo e con backup:

```bash
docker compose -f docker-compose.dev.yml stop backend worker beat
docker compose -f docker-compose.dev.yml run --rm --no-deps backend alembic downgrade -1
docker compose -f docker-compose.dev.yml run --rm --no-deps backend alembic current
```

Prima di riavviare ripristinare codice compatibile con la revisione di destinazione. In produzione usare un'immagine che contenga gli script necessari e il comando Compose del manifest; valutare ogni revisione inversa, evitando un downgrade generico di più cambiamenti alla cieca. Un downgrade non recupera dati già eliminati dalle migrazioni.

Per recuperare dati eliminati occorre il dump. Verificarlo tramite restore su un database separato; pianificare poi l'eventuale ripristino operativo, tenendo conto dei dati acquisiti dopo il backup. Lo script di deploy non automatizza restore o cancellazioni del database.

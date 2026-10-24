# Pannelli, Hugeicons, anteprima email e confidenza AI

Il componente condiviso `ds-icon` usa i pacchetti ufficiali `@hugeicons/angular` e `@hugeicons/core-free-icons` (Stroke Rounded), con import diretti delle sole icone utilizzate. Stroke 1.75 e testo delle azioni medium (500) mantengono il bilanciamento tra icone e voci. Non servono font o richieste CDN. I pannelli hanno un separatore sinistro strutturale grigio `#CBD5E1` da 2 px, indipendente dalla preferenza per bordi ridotti.

La sidebar visualizza solo il nome prima di `@`; l'indirizzo completo rimane nel tooltip. Nella sezione Documenti resta la ricerca testuale (anche per nomi di categorie); il selettore di filtro categorie è stato eliminato. L'associazione delle categorie ai documenti resta disponibile nei moduli.

## Anteprima email

`POST /api/emails/{email_id}/preview` è autenticato, riceve `{ "generated_draft": "..." }` e restituisce `{ "html": "..." }`. Usa lingua e disclaimer dell'email salvata e lo stesso `render_email` utilizzato da Gmail. L'unica differenza nell'HTML è il logo incorporato come data URI al posto del CID MIME. Non modifica il database e non invia email. Testo e link sono trattati dal renderer esistente con escaping HTML.

Nel Review Hub il selettore “Modifica testo / Anteprima email” conserva anche il testo non ancora salvato. L'anteprima viene caricata con debounce di 300 ms in un iframe con script bloccati dalla sandbox e da una Content Security Policy. Il solo permesso same-origin consente alla pagina principale di misurare il documento e adattare l’altezza, senza scrollbar interne. Le risposte a richieste obsolete vengono ignorate; il testo rimane disponibile in caso di errore. La sandbox impedisce interazioni con l'applicazione principale; la preview serve a controllare l'impaginazione.

## Significato di AI confidence

`ai_confidence` è un numero nullable nell'intervallo `[0, 1]`. Per le nuove risposte è la media dei punteggi dei frammenti restituiti dal reranker nelle chiamate `search_knowledge_base` del singolo tentativo di generazione. È una misura di rilevanza del retrieval, **non una probabilità calibrata che la risposta sia corretta**. Il tooltip del badge lo esplicita. Non è ricavata dallo stato dell'email né stimata arbitrariamente dal modello.

I punteggi restano metadati locali della ricerca: non vengono scritti sui chunk del vector store. Se mancano le fonti, il reranker fallisce o l'email è precedente alla modifica, il valore è `null` e il badge mostra “N/D” in indaco. Non vengono rielaborate automaticamente email precedenti.

Badge compatto: 2 px / 7 px di padding, testo 10 px, icona 12 px; verde da 0.8, ambra da 0.5, rosso sotto 0.5. Un valore zero è mostrato come 0%, non come dato assente. Il catalogo Design System usa lo stesso componente della dashboard.

## Migrazione Alembic

Revisione: `e6b9f2a1c430`, precedente: `d4a7e2b9f610`. Aggiunge esclusivamente una colonna nullable e un vincolo di intervallo; i dati precedenti rimangono integri.

Dalla root del progetto, verifiche iniziali:

```bash
docker compose -f docker-compose.dev.yml exec -T backend alembic current
docker compose -f docker-compose.dev.yml exec -T backend alembic heads
docker compose -f docker-compose.dev.yml exec -T db pg_dump -U postgres -Fc unical_support > unical-support-before-ai-confidence.dump
```

Per generare una migrazione equivalente in un ramo in cui questa revisione non esiste ancora (non rigenerarla dopo l'applicazione):

```bash
docker compose -f docker-compose.dev.yml exec -T backend alembic revision --autogenerate -m "add nullable ai confidence to emails"
```

Alembic può non rilevare automaticamente tutti i CHECK: verificare e aggiungere esplicitamente il vincolo nella revisione. Lo script incluso è:

```python
from alembic import op
import sqlalchemy as sa

revision = 'e6b9f2a1c430'
down_revision = 'd4a7e2b9f610'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('emails', sa.Column('ai_confidence', sa.Float(), nullable=True))
    op.create_check_constraint('ck_emails_ai_confidence_range', 'emails', 'ai_confidence >= 0 AND ai_confidence <= 1')


def downgrade():
    op.drop_constraint('ck_emails_ai_confidence_range', 'emails', type_='check')
    op.drop_column('emails', 'ai_confidence')
```

Applicazione e verifiche successive:

```bash
docker compose -f docker-compose.dev.yml exec -T backend alembic upgrade head
docker compose -f docker-compose.dev.yml exec -T backend alembic current
docker compose -f docker-compose.dev.yml exec -T backend alembic check
docker compose -f docker-compose.dev.yml exec -T db psql -U postgres -d unical_support -c 'SELECT count(*), count(ai_confidence) FROM emails;'
docker compose -f docker-compose.dev.yml restart worker
```

Rollback (fermare prima i processi che usano il nuovo modello e ripristinare il codice precedente):

```bash
docker compose -f docker-compose.dev.yml exec -T backend alembic downgrade -1
```

Il downgrade rimuove i punteggi memorizzati, conservando email, bozze e documenti. I test eseguono upgrade e downgrade su database PostgreSQL temporanei, senza retrocedere quello operativo.


## Aggiornamento UX: navigazione, dimensioni e notifiche

Segnalazioni è una voce della sidebar accanto alle Impostazioni; il dialog mantiene descrizione e immagine facoltativa della schermata. Il comando flottante e il calcolo dell’offset del footer sono stati rimossi. L’apertura chiude prima la navigazione mobile e impedisce richieste duplicate durante la cattura.

La sezione è denominata Documenti; la rotta protetta `/knowledge-base` rimane compatibile con i collegamenti precedenti. Documenti e Categorie mostrano icone Hugeicons negli item, con etichette di peso medium 500.

La direttiva `appAutoResize` misura il contenuto iniziale, gli aggiornamenti da codice e l’input manuale. Adatta l’altezza anche al cambio di larghezza, consente la riduzione dopo la cancellazione e lascia lo scorrimento al pannello esterno. L’anteprima misura il body dell’HTML ufficiale con ResizeObserver; non introduce script nel contenuto. La CSP consente soltanto stili inline e immagini incorporate, bloccando script, connessioni e form.

I mittenti vengono separati in nome e indirizzo: le liste mostrano il nome e mantengono il From completo nel tooltip. Se manca il nome, mostrano “Mittente senza nome” e l’indirizzo come testo secondario.

Toast applicativi e catalogo condividono una superficie uniforme semitrasparente: verde per successo, ambra per avviso, rosso per errore; il testo usa una tonalità scura della stessa famiglia. Sono eliminati sfondo neutro e striscia laterale. I messaggi informativi del catalogo mantengono una variante indaco.

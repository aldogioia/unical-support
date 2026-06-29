import time
import random
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from flashrank import Ranker, RerankRequest
from app.core.config import settings
from langchain_postgres import PGVector

embeddings_model = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-2",
    google_api_key=settings.GOOGLE_API_KEY
)

# reranker caricato una volta sola all'avvio
reranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")

_vector_store = None

def init_vector_store():
    global _vector_store
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            _vector_store = PGVector(
                embeddings=embeddings_model,
                collection_name="unical_knowledge_base",
                connection=settings.DATABASE_URL,
                use_jsonb=True,
            )
            break 
        except Exception as e:
            if attempt < max_retries - 1:
                sleep_time = random.uniform(0.5, 2.0)
                print(f"[RAG] Conflitto di inizializzazione DB (Worker paralleli). Ritento tra {sleep_time:.2f}s...")
                time.sleep(sleep_time)
            else:
                print("[RAG] Errore critico: impossibile inizializzare il Vector Store.")
                raise e

def get_vector_store():
    global _vector_store
    if _vector_store is None:
        raise RuntimeError("Vector store non inizializzato. Assicurarsi che lifespan abbia chiamato init_vector_store().")
    return _vector_store


def index_langchain_documents(docs: list, category_name: str = "Generale"):
    for doc in docs:
        doc.metadata["category"] = category_name

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150
    )
    chunks = splitter.split_documents(docs)

    print(f"Indicizzazione di {len(chunks)} frammenti nel Vector DB...")

    # batch piccoli da 5 con pausa di 3 secondi tra ognuno
    batch_size = 5
    vector_store = get_vector_store()
    total_batches = (len(chunks) - 1) // batch_size + 1

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        batch_num = i // batch_size + 1
        retries = 5
        for attempt in range(retries):
            try:
                vector_store.add_documents(batch)
                print(f"  Batch {batch_num}/{total_batches} indicizzato")
                time.sleep(3)
                break
            except Exception as e:
                if "429" in str(e) and attempt < retries - 1:
                    wait = 30 * (attempt + 1)
                    print(f"  Rate limit, aspetto {wait}s...")
                    time.sleep(wait)
                else:
                    raise e

    return len(chunks)


def retrieve_context(query: str, k: int = 4, category_name: str = None) -> str:
    vector_store = get_vector_store()
    search_filter = {"category": category_name} if category_name else None
    candidate_count = k * 3

    try:
        if search_filter:
            candidates = vector_store.similarity_search(query, k=candidate_count, filter=search_filter)
        else:
            candidates = vector_store.similarity_search(query, k=candidate_count)

        if not candidates and search_filter:
            candidates = vector_store.similarity_search(query, k=candidate_count)

    except Exception as e:
        print(f"Errore similarity search: {e}")
        return ""

    if not candidates:
        return ""

    try:
        rerank_request = RerankRequest(
            query=query,
            passages=[{"id": i, "text": doc.page_content} for i, doc in enumerate(candidates)]
        )
        reranked = reranker.rerank(rerank_request)
        top_k_ids = [r["id"] for r in reranked[:k]]
        final_docs = [candidates[i] for i in top_k_ids]
        print(f"Reranking completato: selezionati {len(final_docs)} frammenti finali")

    except Exception as e:
        print(f"Reranking fallito, uso candidati originali: {e}")
        final_docs = candidates[:k]

    return "\n\n---\n\n".join([doc.page_content for doc in final_docs])

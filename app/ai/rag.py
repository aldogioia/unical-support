import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from flashrank import Ranker, RerankRequest
from app.core.config import settings

# ✅ modello di embedding inizializzato subito — non richiede DB
embeddings_model = GoogleGenerativeAIEmbeddings(
    model="text-embedding-001",
    google_api_key=settings.GOOGLE_API_KEY
)

# ✅ reranker caricato una volta sola all'avvio
reranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")

# ✅ lazy: il vector store viene creato solo quando serve
# evita il crash all'avvio se il DB non è ancora pronto
_vector_store = None

def get_vector_store():
    global _vector_store
    if _vector_store is None:
        from langchain_postgres import PGVector
        _vector_store = PGVector(
            embeddings=embeddings_model,
            collection_name="unical_knowledge_base",
            connection=settings.DATABASE_URL,
            use_jsonb=True,
        )
    return _vector_store


def index_langchain_documents(docs: list, category_name: str = "Generale"):
    """
    Riceve documenti LangChain, li taglia in chunk e li salva nel VectorDB.
    """
    for doc in docs:
        doc.metadata["category"] = category_name

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150
    )
    chunks = splitter.split_documents(docs)

    print(f"📚 Indicizzazione di {len(chunks)} frammenti nel Vector DB...")
    get_vector_store().add_documents(chunks)

    return len(chunks)


def retrieve_context(query: str, k: int = 4, category_name: str = None) -> str:
    """
    Recupera i frammenti più rilevanti con metadata filtering e reranking.
    """
    vector_store = get_vector_store()
    search_filter = {"category": category_name} if category_name else None
    candidate_count = k * 3

    try:
        if search_filter:
            candidates = vector_store.similarity_search(query, k=candidate_count, filter=search_filter)
            print(f"🔍 Trovati {len(candidates)} candidati per categoria '{category_name}'")
        else:
            candidates = vector_store.similarity_search(query, k=candidate_count)
            print(f"🔍 Trovati {len(candidates)} candidati globali")

        if not candidates and search_filter:
            print(f"⚠️ Nessun risultato per categoria '{category_name}', ricerca globale...")
            candidates = vector_store.similarity_search(query, k=candidate_count)

    except Exception as e:
        print(f"❌ Errore similarity search: {e}")
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
        print(f"✅ Reranking completato: selezionati {len(final_docs)} frammenti finali")

    except Exception as e:
        print(f"⚠️ Reranking fallito, uso candidati originali: {e}")
        final_docs = candidates[:k]

    return "\n\n---\n\n".join([doc.page_content for doc in final_docs])

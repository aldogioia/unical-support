import os
import time
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from flashrank import Ranker, RerankRequest
from app.core.config import settings

embeddings_model = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-2",
    google_api_key=settings.GOOGLE_API_KEY
)

reranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")
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
    for doc in docs:
        doc.metadata["category"] = category_name

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
    chunks = splitter.split_documents(docs)

    print(f"📚 Indicizzazione di {len(chunks)} frammenti nel Vector DB...")

    # ✅ batch piccoli da 5 con pausa di 3 secondi tra ognuno
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
                print(f"  ✅ Batch {batch_num}/{total_batches} indicizzato")
                time.sleep(3)  # ✅ pausa fissa tra ogni batch
                break
            except Exception as e:
                if "429" in str(e) and attempt < retries - 1:
                    wait = 30 * (attempt + 1)  # ✅ attesa più lunga
                    print(f"  ⏳ Rate limit, aspetto {wait}s...")
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
    except Exception as e:
        print(f"⚠️ Reranking fallito: {e}")
        final_docs = candidates[:k]

    return "\n\n---\n\n".join([doc.page_content for doc in final_docs])

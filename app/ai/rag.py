import time
import random
import json
import re
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document as LangchainDocument
from flashrank import Ranker, RerankRequest
from app.core.config import settings
from langchain_postgres import PGVector

PARAGRAPH_CHUNK_SIZE = 1500
PARAGRAPH_SPLIT_SAFETY_THRESHOLD = 2000

embeddings_model = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-2",
    google_api_key=settings.GOOGLE_API_KEY
)

_reranker_instance = None

def get_reranker():
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = Ranker(model_name="ms-marco-MiniLM-L-12-v2")
    return _reranker_instance
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


GENERAL_CATEGORY_NAME = "Generale"


def _split_into_paragraph_chunks(docs: list) -> list:
    """
    Un paragrafo (blocco separato da riga vuota) = un chunk. Il markdown normalizzato
    prodotto da app.ai.md_formatter è già composto da paragrafi atomici e autosufficienti,
    quindi tagliare sui confini di paragrafo preserva quell'unità invece di troncarla
    a una lunghezza di caratteri arbitraria.
    """
    fallback_splitter = RecursiveCharacterTextSplitter(chunk_size=PARAGRAPH_CHUNK_SIZE, chunk_overlap=300)
    chunks = []
    for doc in docs:
        paragraphs = re.split(r"\n\s*\n", doc.page_content)
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if len(paragraph) > PARAGRAPH_SPLIT_SAFETY_THRESHOLD:
                for sub_chunk in fallback_splitter.split_text(paragraph):
                    chunks.append(LangchainDocument(page_content=sub_chunk, metadata=dict(doc.metadata)))
            else:
                chunks.append(LangchainDocument(page_content=paragraph, metadata=dict(doc.metadata)))
    return chunks


def index_langchain_documents(docs: list, category_names: list[str] | None = None, document_id: str | None = None, reference_url: str | None = None, source_name: str | None = None):
    sorted_names = sorted(set(category_names or []))
    for doc in docs:
        # Lista completa delle categorie del documento (informativa: il filtro in ricerca
        # usa la relazione document_category come fonte di verità).
        doc.metadata["categories"] = sorted_names
        doc.metadata["reference_url"] = reference_url
        doc.metadata["source_name"] = source_name
        if document_id:
            doc.metadata["document_id"] = str(document_id)

    chunks = _split_into_paragraph_chunks(docs)

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


def _normalize_category_names(category_names) -> list[str]:
    if not category_names:
        return []
    if isinstance(category_names, str):
        category_names = [category_names]
    return [n.strip() for n in category_names if n and n.strip()]


def get_document_ids_for_categories(category_names) -> list[str]:
    """
    Restituisce gli ID dei documenti associati ad ALMENO UNA delle categorie indicate
    (match case-insensitive sul nome), considerando tutte le categorie di ciascun documento.
    La categoria "Generale" include anche i documenti senza alcuna categoria.
    """
    from sqlalchemy import func, or_
    from app.db.database import session_scope
    from app.models.document import Document
    from app.models.category import Category

    names = _normalize_category_names(category_names)
    if not names:
        return []
    lowered = [n.lower() for n in names]

    with session_scope() as db:
        conditions = [Document.categories.any(func.lower(Category.name).in_(lowered))]
        if GENERAL_CATEGORY_NAME.lower() in lowered:
            conditions.append(~Document.categories.any())
        rows = db.query(Document.id).filter(or_(*conditions)).all()
        return [str(r[0]) for r in rows]


def retrieve_context(query: str, k: int = 4, category_names: list[str] | str | None = None) -> str:
    vector_store = get_vector_store()
    candidate_count = k * 3

    search_filter = None
    names = _normalize_category_names(category_names)
    if names:
        document_ids = get_document_ids_for_categories(names)
        if not document_ids:
            print(f"[RAG] Nessun documento associato alle categorie {names}.")
            return ""
        search_filter = {"document_id": {"$in": document_ids}}

    try:
        if search_filter:
            candidates = vector_store.similarity_search(query, k=candidate_count, filter=search_filter)
        else:
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
        reranked = get_reranker().rerank(rerank_request)
        final_docs = []
        for result in reranked[:k]:
            # Copy metadata: relevance belongs to this query, not the stored chunk.
            doc = candidates[result["id"]].model_copy(deep=True)
            score = float(result["score"])
            doc.metadata["retrieval_relevance_score"] = score if 0 <= score <= 1 else None
            final_docs.append(doc)
        print(f"Reranking completato: selezionati {len(final_docs)} frammenti finali")

    except Exception as e:
        print(f"Reranking fallito, uso candidati originali: {e}")
        final_docs = candidates[:k]

    return format_source_context(final_docs)


def format_source_context(docs: list) -> str:
    """Keep source attribution with every passage, including legacy chunks."""
    from uuid import UUID
    from app.db.database import session_scope
    from app.models.document import Document

    document_ids = set()
    for doc in docs:
        try:
            document_ids.add(UUID(str(doc.metadata.get("document_id"))))
        except (ValueError, TypeError):
            pass
    sources = {}
    if document_ids:
        with session_scope() as db:
            for source in db.query(Document).filter(Document.id.in_(document_ids)).all():
                sources[str(source.id)] = {
                    "name": source.filename,
                    "reference_url": source.reference_url,
                }

    passages = []
    for doc in docs:
        source = sources.get(str(doc.metadata.get("document_id")), {})
        passages.append(json.dumps({
            "source_name": source.get("name") or doc.metadata.get("source_name") or doc.metadata.get("filename") or "Documento",
            "reference_url": source.get("reference_url", doc.metadata.get("reference_url")),
            "page": doc.metadata.get("page_number", doc.metadata.get("page")),
            "content": doc.page_content,
            "relevance_score": doc.metadata.get("retrieval_relevance_score"),
        }, ensure_ascii=False))
    return "\n\n---\n\n".join(passages)

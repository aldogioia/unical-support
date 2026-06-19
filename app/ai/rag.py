import os
from langchain_postgres import PGVector
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings

# 1. Inizializziamo il modello di Embedding
embeddings_model = GoogleGenerativeAIEmbeddings(
    model="text-embedding-001", 
    google_api_key=settings.GOOGLE_API_KEY
)

# 2. Connettiamo PGVector a PostgreSQL.
vector_store = PGVector(
    embeddings=embeddings_model,
    collection_name="unical_knowledge_base",
    connection=settings.DATABASE_URL,
    use_jsonb=True,
)

def index_langchain_documents(docs: list, category_name: str = "Generale"):
    """
    Riceve i documenti già estratti da LangChain, li taglia in chunk e li salva nel VectorDB.
    """

    for doc in docs:
        doc.metadata["category"] = category_name


    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(docs)

    print(f"Indicizzazione di {len(chunks)} frammenti nel Vector DB...")
    vector_store.add_documents(chunks)
    
    return len(chunks)

def retrieve_context(query: str, k: int = 4) -> str:
    """
    Cerca nel DB i 4 frammenti più simili alla domanda dello studente.
    """
    # Esegue la similarity search vettoriale
    results = vector_store.similarity_search(query, k=k)
    
    # Unisce i frammenti trovati in un unico testo di contesto
    context_text = "\n\n---\n\n".join([doc.page_content for doc in results])
    return context_text
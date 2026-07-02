from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from app.core.config import settings
from app.db.database import session_scope

# Fallback: usati solo se non si riesce a leggere ai_settings dal DB
# (es. tabella non ancora migrata, DB momentaneamente non raggiungibile).
DEFAULT_CLASSIFIER_PROVIDER = "groq"
DEFAULT_CLASSIFIER_MODEL = "openai/gpt-oss-20b"
DEFAULT_RESPONDER_PROVIDER = "google"
DEFAULT_RESPONDER_MODEL = "gemini-3.1-flash-lite"


def _get_current_settings():
    """
    Legge la riga di configurazione corrente da ai_settings.
    Isolato in una propria sessione breve per non interferire con la
    sessione/transazione del task chiamante.
    """
    try:
        from app.services.ai_settings_service import get_settings
        with session_scope() as db:
            row = get_settings(db)
            return {
                "classifier_provider": row.classifier_provider,
                "classifier_model": row.classifier_model,
                "classifier_base_url": row.classifier_base_url,
                "responder_provider": row.responder_provider,
                "responder_model": row.responder_model,
                "responder_base_url": row.responder_base_url,
            }
    except Exception as e:
        print(f"[LLM_FACTORY] Impossibile leggere ai_settings dal DB ({e}), uso i default.")
        return {
            "classifier_provider": DEFAULT_CLASSIFIER_PROVIDER,
            "classifier_model": DEFAULT_CLASSIFIER_MODEL,
            "classifier_base_url": None,
            "responder_provider": DEFAULT_RESPONDER_PROVIDER,
            "responder_model": DEFAULT_RESPONDER_MODEL,
            "responder_base_url": None,
        }


def _build_llm(provider: str, model: str, base_url: str | None, temperature: float):
    """
    Istanzia il client LangChain giusto in base al provider salvato.

    - "groq"   -> ChatGroq (cloud, richiede GROQ_API_KEY)
    - "google" -> ChatGoogleGenerativeAI (cloud, richiede GOOGLE_API_KEY)
    - "local"  -> ChatOpenAI puntato a un server locale compatibile con
                  l'API OpenAI (Ollama, LM Studio, vLLM, llama.cpp server, ecc.)
                  Richiede "base_url" (es. http://host.docker.internal:11434/v1
                  per Ollama). La api_key non serve per la maggior parte dei
                  server locali, ma il client la richiede comunque: si passa
                  un valore placeholder.
    """
    provider = (provider or "").lower().strip()

    if provider == "groq":
        return ChatGroq(temperature=temperature, model_name=model, api_key=settings.GROQ_API_KEY)

    if provider == "google":
        return ChatGoogleGenerativeAI(model=model, temperature=temperature, google_api_key=settings.GOOGLE_API_KEY)

    if provider == "local":
        if not base_url:
            raise ValueError(
                "Provider 'local' selezionato ma nessun base_url configurato. "
                "Imposta l'URL del server locale (es. http://host.docker.internal:11434/v1)."
            )
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            base_url=base_url,
            api_key="not-needed",  # molti server locali ignorano l'api_key, ma il client la richiede comunque
        )

    raise ValueError(f"Provider LLM non supportato: '{provider}'. Usa 'groq', 'google' o 'local'.")


def get_classifier_llm():
    cfg = _get_current_settings()
    return _build_llm(
        provider=cfg["classifier_provider"],
        model=cfg["classifier_model"],
        base_url=cfg["classifier_base_url"],
        temperature=0,
    )

def get_responder_llm():
    cfg = _get_current_settings()
    return _build_llm(
        provider=cfg["responder_provider"],
        model=cfg["responder_model"],
        base_url=cfg["responder_base_url"],
        temperature=0.2,
    )
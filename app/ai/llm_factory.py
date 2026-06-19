from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings

def get_classifier_llm():
    """Usa Groq (Llama 3) per una classificazione fulminea."""
    return ChatGroq(
        temperature=0, 
        model_name="gemma-4-26b-a4b-it", 
        api_key=settings.GROQ_API_KEY
    )

def get_responder_llm():
    """Usa Gemma 4  Pro per la generazione complessa basata sul contesto."""
    return ChatGoogleGenerativeAI(
        model="gemma-4-26b-a4b-it", 
        temperature=0.4, 
        google_api_key=settings.GOOGLE_API_KEY
    )
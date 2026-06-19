from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings

def get_classifier_llm():
    return ChatGroq(
        temperature=0,
        model_name="openai/gpt-oss-20b",
        api_key=settings.GROQ_API_KEY
    )

def get_responder_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        temperature=0.4,
        google_api_key=settings.GOOGLE_API_KEY
    )

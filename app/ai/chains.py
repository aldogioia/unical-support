# app/ai/chains.py
from langchain_core.output_parsers import JsonOutputParser
from app.ai.llm_factory import get_classifier_llm, get_responder_llm
from app.ai.prompts import get_classifier_prompt, get_responder_prompt

def classify_email(sender: str, subject: str, body: str, available_categories: list[str]) -> list:
    """
    Classifica l'email estraendo categorie multiple.
    Ritorna una LISTA di dizionari (JSON parsato).
    """
    categories_str = ", ".join(available_categories)
    llm = get_classifier_llm()
    
    chain = get_classifier_prompt() | llm | JsonOutputParser()
    
    prediction = chain.invoke({
        "CATEGORIES": categories_str,
        "EMAIL_LIST": f"Mittente: {sender}\nOggetto: {subject}\nCorpo: {body}"
    })
    
    return prediction

def generate_draft(enriched_input: str, context: str = "") -> dict:
    """
    Genera la bozza di risposta assemblando template e testo generato.
    Ritorna un DIZIONARIO (JSON parsato).
    """
    llm = get_responder_llm()
    chain = get_responder_prompt() | llm | JsonOutputParser()
    
    draft_json = chain.invoke({
        "ENRICHED_INPUT": enriched_input,
        "CONTEXT": context
    })
    
    return draft_json
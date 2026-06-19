# app/ai/graph.py
from typing import TypedDict, Optional, List, Dict, Any
from langgraph.graph import StateGraph, END
import time

class EmailProcessingState(TypedDict):
    email_id: int
    sender: str
    subject: str
    body: str
    available_categories: list[str]
    predicted_categories_json: Optional[List[Dict[str, Any]]]
    context_retrieved: Optional[str]
    generated_response_json: Optional[Dict[str, Any]]
    final_draft: Optional[str]
    error: Optional[str]
    retry_count: int

def classify_node(state: EmailProcessingState):
    try:
        from app.ai.chains import classify_email
        predictions = classify_email(
            sender=state["sender"], 
            subject=state["subject"], 
            body=state["body"], 
            available_categories=state["available_categories"]
        )
        return {"predicted_categories_json": predictions, "error": None}
    except Exception as e:
        return {"error": f"Classificazione fallita: {str(e)}"}

def retrieve_node(state: EmailProcessingState):
    from app.ai.rag import retrieve_context
    try:
        queries = []
        if state.get("predicted_categories_json"):
            for item in state["predicted_categories_json"]:
                for cat in item.get("categories", []):
                    if cat.get("user_quote"):
                        queries.append(cat["user_quote"])
        
        query_str = f"Oggetto: {state['subject']}\nDomande:\n" + "\n".join(queries) if queries else state['body']
        context = retrieve_context(query=query_str, k=4)
        return {"context_retrieved": context, "error": None}
    except Exception as e:
        return {"error": f"RAG fallito: {str(e)}"}

def generate_node(state: EmailProcessingState):
    from app.ai.chains import generate_draft
    from app.db.database import SessionLocal
    from app.models.category import Category
    
    try:
        enriched_input = f"Oggetto: {state['subject']}\nCorpo: {state['body']}\n\n=== RICHIESTE RILEVATE ===\n"
        db = SessionLocal()
        
        try:
            predicted = state.get("predicted_categories_json", [])
            for item in predicted:
                for cat in item.get("categories", []):
                    cat_name = cat.get("name")
                    quote = cat.get("user_quote")
                    
                    db_category = db.query(Category).filter(Category.name.ilike(cat_name)).first()
                    template_text = "Nessun template disponibile. Generare risposta autonoma."
                    if db_category and db_category.templates:
                        template_text = db_category.templates[0].body_template
                        
                    enriched_input += f"- Categoria: {cat_name}\n  Citazione Utente: '{quote}'\n  Template Fornito: {template_text}\n\n"
        finally:
            db.close()

        draft_json = generate_draft(
            enriched_input=enriched_input,
            context=state.get("context_retrieved", "")
        )
        
        bozza_finale = "Gentile studente,\nin merito alle sue richieste:\n\n"
        
        for answer in draft_json.get("answers", []):
            if answer.get("user_quote"):
                bozza_finale += f"> \"{answer['user_quote']}\"\n\n"
            bozza_finale += f"{answer.get('response_text', '')}\n\n"
            
        bozza_finale += "Cordiali saluti,\nSegreteria Unical"

        return {"generated_response_json": draft_json, "final_draft": bozza_finale, "error": None}
    except Exception as e:
        return {"error": f"Generazione fallita: {str(e)}"}

def error_handler_node(state: EmailProcessingState):
    print(f"[AGENTE] Rilevato errore: {state['error']}. Tentativo {state['retry_count']} di 3.")
    time.sleep(2 ** state["retry_count"])
    return {"retry_count": state["retry_count"] + 1, "error": None}

def route_after_error(state: EmailProcessingState):
    if state["retry_count"] >= 3:
        return END
    if not state.get("predicted_categories_json"):
        return "classify"
    if not state.get("context_retrieved"):
        return "retrieve"
    return "generate"

workflow = StateGraph(EmailProcessingState)

workflow.add_node("classify", classify_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate", generate_node)
workflow.add_node("error_handler", error_handler_node)

workflow.set_entry_point("classify")

workflow.add_conditional_edges("classify", lambda state: "error_handler" if state.get("error") else "retrieve")
workflow.add_conditional_edges("retrieve", lambda state: "error_handler" if state.get("error") else "generate")
workflow.add_conditional_edges("generate", lambda state: "error_handler" if state.get("error") else END)
workflow.add_conditional_edges("error_handler", route_after_error)

app_graph = workflow.compile()
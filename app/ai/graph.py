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
        # raccogliamo le citazioni dello studente per ogni categoria
        predicted = state.get("predicted_categories_json", [])

        if predicted:
            for item in predicted:
                for cat in item.get("categories", []):
                    if cat.get("user_quote"):
                        queries.append(cat["user_quote"])

        query_str = (
            f"Oggetto: {state['subject']}\nDomande:\n" + "\n".join(queries)
            if queries
            else state["body"]
        )

        # passiamo la categoria principale per il metadata filtering
        # se ci sono più categorie usiamo la prima con confidence più alta
        primary_category = None
        if predicted:
            all_cats = [
                cat
                for item in predicted
                for cat in item.get("categories", [])
            ]
            if all_cats:
                # ordina per confidence decrescente e prende la prima
                best = sorted(all_cats, key=lambda x: x.get("confidence", 0), reverse=True)
                primary_category = best[0].get("name")

        context = retrieve_context(
            query=query_str,
            k=4,
            category_name=primary_category
        )

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

# propone un template all'operatore se la risposta era AUTONOMOUS e buona
def propose_template_node(state: EmailProcessingState):
    from app.db.database import SessionLocal
    from app.models.category import Category
    from app.services.template_service import create_template_from_agent

    db = SessionLocal()
    try:
        response_json = state.get("generated_response_json", {})
        answers = response_json.get("answers", [])

        for answer in answers:
            # proponiamo template solo per risposte generate autonomamente
            # quelle da template esistente non ci insegnano nulla di nuovo
            if answer.get("generation_type") != "AUTONOMOUS":
                continue

            category_name = answer.get("category_answered")
            response_text = answer.get("response_text", "")

            # scarto risposte troppo corte o escalation — non sono buoni template
            if len(response_text) < 50 or "inoltrerò" in response_text.lower():
                continue

            db_category = db.query(Category).filter(
                Category.name.ilike(category_name)
            ).first()

            if not db_category:
                continue

            create_template_from_agent(
                db=db,
                name=f"[AI] Template per '{category_name}'",
                body_template=response_text,
                category_ids=[db_category.id],
            )
            print(f"[AGENTE] Nuovo template proposto per la categoria: {category_name}")

        return {"error": None}

    except Exception as e:
        print(f"[AGENTE] Proposta template fallita (non bloccante): {e}")
        return {"error": None}
    finally:
        db.close()

workflow = StateGraph(EmailProcessingState)

workflow.add_node("classify", classify_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate", generate_node)
workflow.add_node("propose_template", propose_template_node)
workflow.add_node("error_handler", error_handler_node)

workflow.set_entry_point("classify")

workflow.add_conditional_edges("classify", lambda state: "error_handler" if state.get("error") else "retrieve")
workflow.add_conditional_edges("retrieve", lambda state: "error_handler" if state.get("error") else "generate")
workflow.add_conditional_edges("generate", lambda state: "error_handler" if state.get("error") else "propose_template")

workflow.add_edge("propose_template", END)

workflow.add_conditional_edges("error_handler", route_after_error)

app_graph = workflow.compile()
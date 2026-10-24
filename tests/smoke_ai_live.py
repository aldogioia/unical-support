"""Opt-in smoke test using real embeddings/LLM, without sending email.

Run: docker compose -f docker-compose.dev.yml exec -T worker python tests/smoke_ai_live.py
The temporary vector collection is deleted in finally; app documents/emails are untouched.
"""
import json
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from langchain_core.documents import Document
    from langchain_core.messages import SystemMessage, HumanMessage
    from langchain_core.tools import tool
    from langchain_postgres import PGVector
    from langgraph.prebuilt import create_react_agent
    from app.ai import rag
    from app.ai.llm_factory import get_responder_llm
    from app.ai.prompts import get_responder_system_prompt
    from app.core.config import settings
    from app.core.email_formatting import prepare_draft, get_ai_disclaimer, DISCLAIMERS
    from app.services.email_renderer import render_email

    source_url = 'https://example.org/unical-support-test'
    collection_name = 'unical_smoke_' + uuid4().hex
    store = PGVector(embeddings=rag.embeddings_model, collection_name=collection_name, connection=settings.DATABASE_URL, use_jsonb=True)
    original_store = rag._vector_store
    captures = []

    @tool
    def search_knowledge_base(query: str, category_names: list[str] | None = None) -> str:
        """Retrieve passages from the isolated synthetic test collection."""
        return rag.retrieve_context(query, k=1)

    @tool
    def save_draft_response(email_id: str, draft_text: str, response_language: str | None = None, ai_disclaimer: str | None = None) -> str:
        """Capture a draft for this smoke test. Pass ISO response_language and, for languages other than it/en/es/fr/de/pt, the translated ai_disclaimer. The system adds the supervised transparency note separately at send time."""
        captures.append(dict(language=response_language, draft=prepare_draft(draft_text, response_language, ai_disclaimer)))
        return 'Bozza salvata con successo.'

    @tool
    def escalate_to_human(email_id: str, reason: str) -> str:
        """Request manual handling if the knowledge base cannot answer."""
        raise AssertionError('Escalation inattesa per una richiesta coperta dalla fonte sintetica: ' + reason)

    try:
        rag._vector_store = store
        rag.index_langchain_documents(
            [Document(page_content='DOCUMENTO ESCLUSIVAMENTE DI COLLAUDO, SENZA VALORE AMMINISTRATIVO. Il codice di verifica del collaudo è UNICAL-COLLAUDO-7429. Questa informazione serve soltanto a verificare la pipeline e non descrive procedure reali della segreteria.')],
            reference_url=source_url, source_name='Documento sintetico di collaudo',
        )
        context = rag.retrieve_context('Qual è il codice di verifica del collaudo?', k=1)
        assert source_url in context and 'UNICAL-COLLAUDO-7429' in context
        print(json.dumps({'check': 'embedding_retrieval_reference_url', 'ok': True}), flush=True)
        llm = get_responder_llm()
        tools = [search_knowledge_base, save_draft_response, escalate_to_human]
        cases = [
            ('it', 'Ciao, qual è il codice di verifica nel documento sintetico di collaudo? Includi il link alla fonte.'),
            ('en', 'Hello, what is the verification code in the synthetic test document? Please include a link to the source.'),
            ('es', 'Hola, ¿cuál es el código de verificación del documento sintético de prueba? Incluye el enlace a la fuente.'),
        ]
        for language, body in cases:
            before = len(captures)
            agent = create_react_agent(llm, tools)
            agent.invoke({'messages': [SystemMessage(content=get_responder_system_prompt()), HumanMessage(content=f"Email ID: {uuid4()}\nCategorie assegnate: Generale\nTesto: {body}")]}, config={'recursion_limit': 15})
            assert len(captures) > before, 'Il modello non ha salvato la bozza'
            result = captures[-1]
            assert result['language'] == language, f"Lingua inattesa: {result['language']}"
            assert not result['draft'].startswith(DISCLAIMERS[language]), 'Disclaimer duplicato nel corpo'
            rendered = render_email(result['draft'], language, get_ai_disclaimer(language))
            assert rendered.plain_text.startswith(DISCLAIMERS[language]), 'Nota IA mancante in apertura'
            assert source_url in result['draft'], 'Citazione URL mancante'
            assert 'UNICAL-COLLAUDO-7429' in result['draft'], 'Informazione recuperata mancante'
            print(json.dumps({'check': 'real_responder', 'language': language, 'supervised_disclaimer_at_top': True, 'reference_url_cited': True, 'retrieved_fact_present': True, 'draft': result['draft']}, ensure_ascii=False), flush=True)
    finally:
        rag._vector_store = original_store
        store.delete_collection()
        print('Raccolta vettoriale temporanea eliminata; nessuna email inviata.', flush=True)


if __name__ == '__main__':
    main()

"""Real responder checks using synthetic retrieval only. No emails, transport or application records are changed."""
import json
import re
import sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from langchain_core.messages import SystemMessage, HumanMessage
    from langchain_core.tools import tool
    from langgraph.prebuilt import create_react_agent
    from app.ai.llm_factory import get_responder_llm
    from app.ai.prompts import get_responder_system_prompt
    from app.core.email_formatting import prepare_draft
    captures = []
    cases = [
        ('en', 'Informazioni sul collaudo', 'Hello, what is the code in the test document?', True),
        ('en', 'Codice di verifica', 'Hello, what is the test code?\nHola, también quiero saber el código de prueba.', True),
        ('es', 'Test code', 'Hola, ¿cuál es el código del documento de prueba?\nHello, what is the test code?', True),
        ('it', 'English test request', 'Buongiorno, qual è il codice del documento di collaudo?\nHello, what is the test code?', True),
        ('en', 'Richiesta italiana', 'Hello, what is the code in the test document?', False),
    ]
    forbidden = {'en': r'\b(buongiorno|cordiali|gracias|atentamente|saludos|hola|ciao)\b',
                 'it': r'\b(hello|thanks|regards|gracias|atentamente|hola)\b',
                 'es': r'\b(hello|thanks|regards|buongiorno|cordiali|ciao)\b'}
    for language, subject, body, linked in cases:
        url = 'https://example.org/unical-language-test' if linked else None
        source_name = 'Test source' if linked else 'FonteSenzaLink_UNICAL.txt'
        @tool
        def search_knowledge_base(query: str, category_names: list[str] | None = None) -> str:
            """Retrieve the synthetic test document. Respect citation_allowed and reference_url."""
            return json.dumps(dict(content='The verification code is UNICAL-COLLAUDO-7429. Synthetic test data only.', source_name=source_name, reference_url=url, citation_allowed=bool(url)))
        @tool
        def save_draft_response(email_id: str, draft_text: str, response_language: str | None = None, ai_disclaimer: str | None = None) -> str:
            """Capture the reply in the first language of the email body. Pass ISO response_language."""
            captures.append((response_language, prepare_draft(draft_text, response_language, ai_disclaimer)))
            return 'Draft saved.'
        @tool
        def escalate_to_human(email_id: str, reason: str) -> str:
            """Escalate only if the synthetic source cannot answer."""
            raise AssertionError('Unexpected escalation: ' + reason)
        agent = create_react_agent(get_responder_llm(), [search_knowledge_base, save_draft_response, escalate_to_human])
        before = len(captures)
        agent.invoke({'messages': [SystemMessage(content=get_responder_system_prompt()), HumanMessage(content=f'Email ID: {uuid4()}\nOggetto (non determina la lingua): {subject}\nCORPO DEL MESSAGGIO:\n{body}')]}, config={'recursion_limit': 15})
        assert len(captures) > before, 'No saved draft'
        actual, draft = captures[-1]
        assert actual == language, (language, actual)
        assert not re.search(forbidden[language], draft, re.IGNORECASE), draft
        assert 'UNICAL-COLLAUDO-7429' in draft
        if linked:
            assert url in draft
        else:
            assert source_name not in draft and not re.search(r'https?://', draft)
        print(json.dumps(dict(language=language, linked=linked, single_language=True, body_wins_over_subject=True, ok=True, draft=draft), ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()

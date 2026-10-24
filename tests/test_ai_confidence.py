import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from app.core.ai_confidence import retrieval_confidence
from app.schemas.email import EmailResponse


def tool_message(*scores, **kwargs):
    return SimpleNamespace(type='tool', name='search_knowledge_base', content='\n\n---\n\n'.join(json.dumps({'relevance_score': score}) for score in scores), **kwargs)


def test_confidence_uses_only_real_retrieval_results_and_preserves_zero():
    assert retrieval_confidence([tool_message(0.8, 1), tool_message(0.6)]) == 0.8
    assert retrieval_confidence([tool_message(0)]) == 0
    assert retrieval_confidence([tool_message(1)]) == 1
    assert retrieval_confidence([SimpleNamespace(type='human', name='search_knowledge_base', content='{"relevance_score":1}')]) is None
    assert retrieval_confidence([SimpleNamespace(type='tool', name='save_draft_response', content='{"relevance_score":1}')]) is None


def test_legacy_missing_fallback_and_invalid_scores_are_unknown():
    assert retrieval_confidence([]) is None
    assert retrieval_confidence([tool_message(None, '0.9', True, -1, 2, float('nan'), float('inf'))]) is None
    assert retrieval_confidence([SimpleNamespace(type='tool', name='search_knowledge_base', content='No sources')]) is None


def test_email_contract_is_nullable_and_rejects_out_of_range_values():
    from uuid import uuid4
    data = dict(id=uuid4(), gmail_id='gmail-1', sender='student@example.org', status='DRAFT')
    assert EmailResponse(**data).ai_confidence is None
    assert EmailResponse(**data, ai_confidence=0.96).ai_confidence == 0.96
    for score in [-0.1, 1.1, float('nan')]:
        with pytest.raises(ValidationError):
            EmailResponse(**data, ai_confidence=score)


def test_reranker_scores_are_query_local_and_fallback_is_unknown():
    from langchain_core.documents import Document
    from app.ai import rag
    from unittest.mock import MagicMock
    source = Document(page_content='Regole', metadata={})
    store, ranker = MagicMock(), MagicMock()
    store.similarity_search.return_value = [source]
    ranker.rerank.return_value = [{'id': 0, 'score': 0.93}]
    with patch.object(rag, 'get_vector_store', return_value=store), patch.object(rag, 'get_reranker', return_value=ranker):
        passage = json.loads(rag.retrieve_context('Domanda'))
        assert passage['relevance_score'] == 0.93
        assert source.metadata == {}
        ranker.rerank.side_effect = RuntimeError('offline')
        assert json.loads(rag.retrieve_context('Domanda'))['relevance_score'] is None


def test_responder_persists_confidence_from_its_own_retrieval_messages():
    from uuid import uuid4
    from unittest.mock import MagicMock
    from app.tasks.email_tasks import respond_email_task
    from app.models.enumerators.enumerators import EmailStatus
    email = SimpleNamespace(id=uuid4(), status=EmailStatus.TO_RESPOND, sender='student@example.org',
                            subject='Domanda', body='Regole', gmail_id='gmail-1', categories=[], ai_confidence=0.1)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = email
    agent = MagicMock()
    def generate(*args, **kwargs):
        assert email.ai_confidence is None
        email.status = EmailStatus.DRAFT
        return {'messages': [tool_message(0.9, 0.8)]}
    agent.invoke.side_effect = generate
    with patch('app.tasks.email_tasks.session_scope') as session, \
         patch('app.ai.llm_factory.get_responder_llm'), \
         patch('langgraph.prebuilt.create_react_agent', return_value=agent):
        session.return_value.__enter__.return_value = db
        assert respond_email_task.run(email.id) is True
    assert email.ai_confidence == 0.85

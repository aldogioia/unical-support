import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4
import pytest
from langchain_core.documents import Document
from app.ai.rag import format_source_context
from app.ai.prompts import get_responder_system_prompt
from app.ai.tools import processing_tools


@pytest.mark.parametrize('url', [None, '', 'javascript:alert(1)', 'ftp://example.org/a', 123])
def test_missing_and_invalid_document_urls_are_not_citable(url):
    passage = json.loads(format_source_context([Document(page_content='Fatto documentale', metadata={'source_name': 'Guida senza link', 'reference_url': url})]))
    assert passage['reference_url'] is None
    assert passage['citation_allowed'] is False


def test_database_link_removal_wins_over_stale_vector_metadata():
    identifier = uuid4()
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [SimpleNamespace(id=identifier, filename='Guida', reference_url=None)]
    with patch('app.db.database.session_scope') as scope:
        scope.return_value.__enter__.return_value = db
        passage = json.loads(format_source_context([Document(page_content='Fatto', metadata={'document_id': str(identifier), 'reference_url': 'https://example.org/stale'})]))
    assert passage['reference_url'] is None and not passage['citation_allowed']


def test_bound_agent_rejects_uncited_names_invented_links_and_saving_without_retrieval():
    identifier = uuid4()
    tools = {operation.name: operation for operation in processing_tools(identifier, 'token', 'respond')}
    base = dict(email_id=str(identifier), response_language='en')
    assert 'Consulta prima' in tools['save_draft_response'].invoke(dict(base, draft_text='Hello'))
    context = '\n\n---\n\n'.join(json.dumps(item) for item in [
        dict(source_name='Fonte senza link.txt', reference_url=None, content='Code TEST-42'),
        dict(source_name='Fonte verificabile', reference_url='https://example.org/a_(b)', content='Code TEST-42'),
    ])
    with patch('app.ai.tools.retrieve_context', return_value=context), patch('app.ai.tools._save_draft_response', return_value='Saved') as save:
        tools['search_knowledge_base'].invoke(dict(query='Test'))
        assert 'Non citare' in tools['save_draft_response'].invoke(dict(base, draft_text='Fonte senza link.txt: TEST-42'))
        assert 'Link non presente' in tools['save_draft_response'].invoke(dict(base, draft_text='TEST-42 https://example.org/invented'))
        assert tools['save_draft_response'].invoke(dict(base, draft_text='The code is TEST-42. Fonte verificabile: https://example.org/a_(b).')) == 'Saved'
        save.assert_called_once()


def test_prompt_gives_body_first_language_priority_over_subject_and_majority_language():
    prompt = get_responder_system_prompt()
    assert 'ESCLUSIVAMENTE dal CORPO' in prompt
    assert 'PRIMA lingua riconoscibile' in prompt
    assert 'Non scegliere la lingua maggioritaria' in prompt
    assert 'strettamente UNILINGUA' in prompt
    assert 'NON citare' in prompt
    assert 'body_language_is_authoritative' in prompt

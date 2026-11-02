"""Ripiego senza tool calling (app/ai/fallback.py): nessun database reale né modello reale."""
import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage
from sqlalchemy.exc import OperationalError

from app.ai import fallback
from app.models.category import Category
from app.models.email import Email, EmailStatus


def make_email(status, **kwargs):
    values = dict(id=uuid4(), status=status, sender='student@example.org', subject='Domanda',
                  body='Quando scade la seconda rata?', categories=[], processing_token='tok',
                  processing_generation=0, manually_edited=False, ai_confidence=None)
    values.update(kwargs)
    return SimpleNamespace(**values)


def fake_db(email, categories=()):
    db = MagicMock()
    def query(model):
        q = MagicMock()
        q.filter.return_value.populate_existing.return_value.first.return_value = email
        q.filter.return_value.populate_existing.return_value.with_for_update.return_value.first.return_value = email
        q.all.return_value = list(categories)
        return q
    db.query.side_effect = query
    @contextmanager
    def scope():
        yield db
    return scope


def scripted_llm(*replies):
    llm = MagicMock()
    llm.invoke.side_effect = [AIMessage(content=reply) for reply in replies]
    return llm


def passage(url='https://www.unical.it/tasse', name='Regolamento tasse', score=0.8):
    return json.dumps({'source_name': name, 'reference_url': url, 'citation_allowed': bool(url),
                       'page': None, 'content': 'La seconda rata scade il 31 marzo.', 'relevance_score': score})


# ------------------------------------------------------------------ quando scatta

def test_model_errors_trigger_fallback_but_infrastructure_errors_do_not():
    request = httpx.Request('POST', 'http://localhost:11434/v1/chat/completions')
    tools_refused = openai.BadRequestError('does not support tools', response=httpx.Response(400, request=request), body=None)
    assert fallback.is_model_failure(tools_refused)
    assert fallback.is_model_failure(RuntimeError('L’agente non ha completato il salvataggio'))
    assert not fallback.is_model_failure(openai.APIConnectionError(request=request))
    assert not fallback.is_model_failure(openai.APITimeoutError(request=request))
    assert not fallback.is_model_failure(OperationalError('select', {}, Exception('db down')))
    assert not fallback.is_model_failure(ConnectionRefusedError())
    try:
        try:
            raise ConnectionRefusedError()
        except ConnectionRefusedError as inner:
            raise RuntimeError('wrapped') from inner
    except RuntimeError as chained:
        assert not fallback.is_model_failure(chained)


def test_infrastructure_error_returns_original_exception_without_running_fallback():
    error = openai.APIConnectionError(request=httpx.Request('POST', 'http://x'))
    with patch.object(fallback, 'run_fallback') as run:
        assert fallback.attempt_fallback(error, uuid4(), 'classify', 'tok', 0) == (False, error)
    run.assert_not_called()


def test_failed_fallback_keeps_the_original_exception_for_celery_retries():
    original = RuntimeError('agente senza tool')
    with patch.object(fallback, 'run_fallback', side_effect=fallback.FallbackError('JSON non valido')):
        assert fallback.attempt_fallback(original, uuid4(), 'respond', 'tok', 0) == (False, original)


def test_email_no_longer_owned_is_left_to_the_existing_error_path():
    email = make_email(EmailStatus.TO_RESPOND, processing_token='altro-worker')
    with patch.object(fallback, 'session_scope', fake_db(email)), \
         patch.object(fallback, 'get_responder_llm') as llm:
        assert fallback.run_fallback(email.id, 'respond', 'tok', 0) is None
    llm.assert_not_called()


# ------------------------------------------------------------------ lettura del JSON

@pytest.mark.parametrize('text', [
    '{"category_names": ["Tasse e contributi"]}',
    'Ecco il risultato:\n```json\n{"category_names": ["Tasse e contributi"]}\n```',
    '<think>ragiono sulle categorie {non json}</think>\n{"category_names": ["Tasse e contributi"]}',
    'Certo! {"category_names": ["Tasse e contributi"]} Spero sia utile.',
])
def test_json_is_extracted_from_common_model_outputs(text):
    data, problem = fallback._parse_json(fallback._response_text(AIMessage(content=text)))
    assert problem is None and data == {'category_names': ['Tasse e contributi']}


def test_raw_newlines_inside_strings_are_accepted():
    data, _ = fallback._parse_json('{"action": "draft", "draft_text": "Ciao,\nla rata scade."}')
    assert data['draft_text'] == 'Ciao,\nla rata scade.'


def test_list_content_from_providers_is_joined():
    response = AIMessage(content=[{'type': 'text', 'text': '{"a": '}, {'type': 'text', 'text': '1}'}])
    assert fallback._parse_json(fallback._response_text(response))[0] == {'a': 1}


# ------------------------------------------------------------------ classificazione

def test_classification_corrects_the_model_and_assigns_canonical_names():
    email = make_email(EmailStatus.TO_CLASSIFY)
    catalog = [SimpleNamespace(name='Mobilita internazionale', description='Erasmus'),
               SimpleNamespace(name='Tasse e contributi', description='Rate')]
    llm = scripted_llm('Direi Erasmus.', '{"category_names": ["mobilità internazionale", "Inventata"]}')
    with patch.object(fallback, 'session_scope', fake_db(email, catalog)), \
         patch.object(fallback, 'get_classifier_llm', return_value=llm), \
         patch.object(fallback, '_assign_categories') as assign:
        assert fallback.run_fallback(email.id, 'classify', 'tok', 0) is True
    assign.assert_called_once_with(email.id, ['Mobilita internazionale'], 'tok')
    second_call = llm.invoke.call_args_list[1].args[0]
    assert 'JSON' in second_call[-1].content
    assert 'Erasmus' in second_call[1].content


def test_classification_gives_up_after_the_allowed_attempts():
    email = make_email(EmailStatus.TO_CLASSIFY)
    catalog = [SimpleNamespace(name='Generale', description='')]
    llm = scripted_llm('boh', 'ancora no', '{"category_names": ["Nessuna"]}')
    with patch.object(fallback, 'session_scope', fake_db(email, catalog)), \
         patch.object(fallback, 'get_classifier_llm', return_value=llm), \
         patch.object(fallback, '_assign_categories') as assign, \
         pytest.raises(fallback.FallbackError):
        fallback.run_fallback(email.id, 'classify', 'tok', 0)
    assign.assert_not_called()
    assert llm.invoke.call_count == fallback.MAX_ATTEMPTS


# ------------------------------------------------------------------ risposta

def test_response_rejects_invented_links_then_saves_and_stores_confidence():
    email = make_email(EmailStatus.TO_RESPOND, categories=[SimpleNamespace(name='Tasse e contributi')])
    bad = json.dumps({'action': 'draft', 'draft_text': 'Vedi https://inventato.example/x', 'response_language': 'it'})
    good = json.dumps({'action': 'draft', 'draft_text': 'La seconda rata scade il 31 marzo.\n\nRegolamento tasse: https://www.unical.it/tasse',
                       'response_language': 'it', 'ai_disclaimer': None})
    llm = scripted_llm(bad, good)
    def save(email_id, draft, language, disclaimer, token):
        email.status = EmailStatus.DRAFT
        return fallback.SAVED_OK
    with patch.object(fallback, 'session_scope', fake_db(email)), \
         patch.object(fallback, 'get_responder_llm', return_value=llm), \
         patch.object(fallback, 'retrieve_context', return_value=passage(score=0.8)) as search, \
         patch.object(fallback, '_save_draft_response', side_effect=save) as saved:
        assert fallback.run_fallback(email.id, 'respond', 'tok', 0) is True
    search.assert_called_once()
    assert search.call_args.kwargs['category_names'] == ['Tasse e contributi']
    assert saved.call_args.args[1].endswith('https://www.unical.it/tasse')
    assert saved.call_args.args[2] == 'it' and saved.call_args.args[3] is None
    assert 'reference_url' in llm.invoke.call_args_list[1].args[0][-1].content
    assert email.ai_confidence == 0.8


def test_response_repeats_search_without_filter_and_escalates_when_nothing_is_found():
    email = make_email(EmailStatus.TO_RESPOND, categories=[SimpleNamespace(name='Tasse e contributi')])
    with patch.object(fallback, 'session_scope', fake_db(email)), \
         patch.object(fallback, 'get_responder_llm') as llm, \
         patch.object(fallback, 'retrieve_context', return_value='') as search, \
         patch.object(fallback, '_escalate_to_human') as escalate:
        assert fallback.run_fallback(email.id, 'respond', 'tok', 0) is True
    assert [c.kwargs['category_names'] for c in search.call_args_list] == [['Tasse e contributi'], None]
    escalate.assert_called_once()
    assert escalate.call_args.args[2] == 'tok'
    llm.assert_not_called()


def test_model_can_choose_escalation():
    email = make_email(EmailStatus.TO_RESPOND)
    llm = scripted_llm('{"action": "escalate", "reason": "Minaccia di azioni legali"}')
    with patch.object(fallback, 'session_scope', fake_db(email)), \
         patch.object(fallback, 'get_responder_llm', return_value=llm), \
         patch.object(fallback, 'retrieve_context', return_value=passage()), \
         patch.object(fallback, '_escalate_to_human') as escalate:
        assert fallback.run_fallback(email.id, 'respond', 'tok', 0) is True
    escalate.assert_called_once_with(email.id, 'Minaccia di azioni legali', 'tok')


def test_save_errors_are_sent_back_to_the_model():
    email = make_email(EmailStatus.TO_RESPOND)
    first = json.dumps({'action': 'draft', 'draft_text': 'Hallo', 'response_language': 'nl'})
    second = json.dumps({'action': 'draft', 'draft_text': 'Hallo', 'response_language': 'nl', 'ai_disclaimer': 'Vertaling'})
    llm = scripted_llm(first, second)
    with patch.object(fallback, 'session_scope', fake_db(email)), \
         patch.object(fallback, 'get_responder_llm', return_value=llm), \
         patch.object(fallback, 'retrieve_context', return_value=passage()), \
         patch.object(fallback, '_save_draft_response', side_effect=['Serve ai_disclaimer tradotto.', fallback.SAVED_OK]) as saved:
        assert fallback.run_fallback(email.id, 'respond', 'tok', 0) is True
    assert saved.call_count == 2
    assert 'Serve ai_disclaimer tradotto.' in llm.invoke.call_args_list[1].args[0][-1].content


# ------------------------------------------------------------------ aggancio in email_tasks

def _task_patches(email, agent):
    db = MagicMock()
    db.query.return_value.filter.return_value.populate_existing.return_value.with_for_update.return_value.first.return_value = email
    session = patch('app.tasks.email_tasks.session_scope')
    return db, session


def test_agent_without_tool_calls_is_completed_by_the_fallback():
    from app.tasks.email_tasks import classify_email_task
    email = make_email(EmailStatus.TO_CLASSIFY, processing_token=None, processing_started_at=None)
    agent = MagicMock()
    agent.invoke.return_value = {'messages': [AIMessage(content='Categoria: Tasse')]}
    db, session = _task_patches(email, agent)
    with session as scope, \
         patch('app.ai.llm_factory.get_classifier_llm'), \
         patch('langgraph.prebuilt.create_react_agent', return_value=agent), \
         patch('app.ai.fallback.run_fallback', return_value=True) as run:
        scope.return_value.__enter__.return_value = db
        assert classify_email_task.run(email.id) is True
    assert run.call_args.args[1] == 'classify'
    assert run.call_args.args[2] == email.processing_token


def test_tool_calling_success_never_touches_the_fallback():
    from app.tasks.email_tasks import classify_email_task
    email = make_email(EmailStatus.TO_CLASSIFY, processing_token=None, processing_started_at=None)
    agent = MagicMock()
    def classify(*args, **kwargs):
        email.status = EmailStatus.TO_RESPOND
        return {'messages': []}
    agent.invoke.side_effect = classify
    db, session = _task_patches(email, agent)
    with session as scope, \
         patch('app.ai.llm_factory.get_classifier_llm'), \
         patch('langgraph.prebuilt.create_react_agent', return_value=agent), \
         patch('app.ai.fallback.attempt_fallback') as attempt:
        scope.return_value.__enter__.return_value = db
        assert classify_email_task.run(email.id) is True
    attempt.assert_not_called()

"""Token-only LangChain → Langfuse integration, without message/document content."""
from contextlib import contextmanager
from contextvars import ContextVar
import logging
import os
from threading import Lock
from uuid import uuid4
from langchain_core.callbacks import BaseCallbackHandler
from app.core.config import settings

logger = logging.getLogger(__name__)
_job = ContextVar('ai_observability_job', default=None)
_client = None
_client_pid = None
_client_lock = Lock()


def get_observability_client():
    global _client, _client_pid
    if not settings.LANGFUSE_ENABLED:
        return None
    pid = os.getpid()
    with _client_lock:
        if _client_pid == pid:
            return _client
        _client_pid, _client = pid, None
        if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY.get_secret_value():
            logger.warning('Langfuse abilitato ma chiavi mancanti: tracciamento disattivato.')
            return None
        try:
            from langfuse import Langfuse
            _client = Langfuse(public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY.get_secret_value(),
                base_url=settings.LANGFUSE_BASE_URL, environment=settings.LANGFUSE_ENVIRONMENT,
                release=settings.LANGFUSE_RELEASE or None, timeout=2, flush_interval=2, sample_rate=1.0)
        except Exception as exc:
            logger.warning('Inizializzazione Langfuse fallita (%s).', type(exc).__name__)
        return _client


@contextmanager
def ai_job(kind, identifier, stage, generation=None):
    token = _job.set(dict(kind=kind, entity_id=str(identifier), stage=stage,
                          trace_id=uuid4().hex, generation=generation))
    try:
        yield
    finally:
        _job.reset(token)


def flush_observability():
    if _client is not None and _client_pid == os.getpid():
        try:
            _client.flush()
        except Exception as exc:
            logger.warning('Flush Langfuse fallito (%s).', type(exc).__name__)


def _count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def token_usage(response):
    """Use actual provider usage once; missing counts are not estimated as zero."""
    result = {}
    for generations in getattr(response, 'generations', []) or []:
        if not generations:
            continue
        usage = getattr(getattr(generations[0], 'message', None), 'usage_metadata', None) or {}
        for source, target in [('input_tokens', 'input'), ('output_tokens', 'output'), ('total_tokens', 'total')]:
            value = _count(usage.get(source))
            if value is not None:
                result[target] = result.get(target, 0) + value
        cached = _count((usage.get('input_token_details') or {}).get('cache_read'))
        if cached is not None:
            result['input_cache_read'] = result.get('input_cache_read', 0) + cached
            if 'input' in result:
                result['input'] = max(0, result['input'] - cached)
    if result:
        return result
    raw = getattr(response, 'llm_output', None) or {}
    usage = raw.get('token_usage') or raw.get('usage') or raw.get('usage_metadata') or {}
    for target, names in [('input', ['prompt_tokens', 'input_tokens', 'prompt_token_count']),
                          ('output', ['completion_tokens', 'output_tokens', 'candidates_token_count']),
                          ('total', ['total_tokens', 'total_token_count'])]:
        value = next((_count(usage[key]) for key in names if _count(usage.get(key)) is not None), None)
        if value is not None:
            result[target] = value
    cached = _count((usage.get('prompt_tokens_details') or {}).get('cached_tokens'))
    if cached is not None:
        result['input_cache_read'] = cached
        if 'input' in result:
            result['input'] = max(0, result['input'] - cached)
    return result


class TokenUsageCallback(BaseCallbackHandler):
    """Exports only model, identifiers, timing and usage, never content or errors."""
    raise_error = False

    def __init__(self, client, provider, model, stage):
        self.client, self.provider, self.model = client, provider, model
        self.job = dict(_job.get() or {'kind': 'llm', 'stage': stage, 'trace_id': uuid4().hex})
        self.runs, self.lock = {}, Lock()

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        self._start(run_id)

    def on_llm_start(self, serialized, prompts, *, run_id, **kwargs):
        self._start(run_id)

    def _start(self, run_id):
        try:
            observation = self.client.start_observation(as_type='generation',
                name=f"{self.job['kind']}.{self.job['stage']}", trace_context={'trace_id': self.job['trace_id']},
                model=self.model, metadata={**{k: v for k, v in self.job.items() if k != 'trace_id' and v is not None},
                                            'provider': self.provider, 'content_recorded': False})
            with self.lock:
                self.runs[run_id] = observation
        except Exception as exc:
            logger.warning('Avvio osservazione Langfuse fallito (%s).', type(exc).__name__)

    def on_llm_end(self, response, *, run_id, **kwargs):
        self._finish(run_id, usage=token_usage(response))

    def on_llm_error(self, error, *, run_id, **kwargs):
        self._finish(run_id, error_type=type(error).__name__)

    def _finish(self, run_id, usage=None, error_type=None):
        with self.lock:
            observation = self.runs.pop(run_id, None)
        if observation is None:
            return
        try:
            if error_type:
                observation.update(level='ERROR', status_message=error_type)
            else:
                observation.update(usage_details=usage or None, metadata={'usage_reported': bool(usage)})
        except Exception as exc:
            logger.warning('Aggiornamento Langfuse fallito (%s).', type(exc).__name__)
        finally:
            try:
                observation.end()
            except Exception:
                logger.warning('Chiusura osservazione Langfuse fallita.')


def llm_callbacks(provider, model, stage):
    client = get_observability_client()
    return [TokenUsageCallback(client, provider, model, stage)] if client is not None else []

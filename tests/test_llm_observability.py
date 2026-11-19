"""Token accounting, failure isolation and proof that content is never exported."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4
from pydantic import SecretStr
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from app.core import llm_observability as telemetry
from app.core.config import settings


def response(usage=None, raw=None):
    return LLMResult(generations=[[ChatGeneration(message=AIMessage(content='PRIVATE_STUDENT_BODY', usage_metadata=usage))]], llm_output=raw)


def test_counts_normalized_usage_once_and_separates_cached_input():
    result = response({'input_tokens':100, 'output_tokens':30, 'total_tokens':130,
                       'input_token_details':{'cache_read':40}}, {'token_usage':{'prompt_tokens':100, 'completion_tokens':30}})
    assert telemetry.token_usage(result) == {'input':60, 'input_cache_read':40, 'output':30, 'total':130}


def test_raw_provider_usage_zero_and_missing_usage_are_distinct():
    assert telemetry.token_usage(response(raw={'token_usage':{'prompt_tokens':0, 'completion_tokens':0, 'total_tokens':0}})) == {'input':0,'output':0,'total':0}
    assert telemetry.token_usage(response()) == {}
    assert telemetry.token_usage(response(raw={'usage':{'input_tokens':True, 'output_tokens':-1}})) == {}


def test_callback_exports_tokens_but_never_messages_tool_payloads_or_error_text():
    client = MagicMock()
    with telemetry.ai_job('email', uuid4(), 'respond', 4):
        callback = telemetry.TokenUsageCallback(client, 'local', 'test-model', 'respond')
    run = uuid4()
    callback.on_chat_model_start({'secret':'PRIVATE_STUDENT_BODY'}, ['PRIVATE_STUDENT_BODY'], run_id=run,
                                 metadata={'private':'PRIVATE_STUDENT_BODY'})
    callback.on_llm_end(response({'input_tokens':12,'output_tokens':3,'total_tokens':15}), run_id=run)
    observation = client.start_observation.return_value
    observation.update.assert_called_once_with(usage_details={'input':12,'output':3,'total':15}, metadata={'usage_reported':True})
    observation.end.assert_called_once()
    other = uuid4()
    callback.on_chat_model_start({}, ['PRIVATE_STUDENT_BODY'], run_id=other)
    callback.on_llm_error(RuntimeError('PRIVATE_STUDENT_BODY'), run_id=other)
    assert 'PRIVATE_STUDENT_BODY' not in repr(client.mock_calls)
    assert 'RuntimeError' in repr(client.mock_calls)


def test_unavailable_langfuse_cannot_break_model_response():
    client = MagicMock()
    client.start_observation.side_effect = RuntimeError('PRIVATE_STUDENT_BODY')
    callback = telemetry.TokenUsageCallback(client, 'google', 'test-model', 'respond')
    run = uuid4()
    callback.on_chat_model_start({}, ['PRIVATE_STUDENT_BODY'], run_id=run)
    callback.on_llm_end(response(), run_id=run)
    client.start_observation.side_effect = None
    client.start_observation.return_value.update.side_effect = RuntimeError('unreachable')
    callback.on_chat_model_start({}, [], run_id=run)
    callback.on_llm_end(response(), run_id=run)
    client.start_observation.return_value.end.assert_called_once()


def test_disabled_observability_does_not_initialize_sdk():
    with patch.object(settings, 'LANGFUSE_ENABLED', False), patch('langfuse.Langfuse') as sdk:
        assert telemetry.llm_callbacks('local', 'test', 'respond') == []
    sdk.assert_not_called()


def test_client_is_created_per_process_and_reads_secret_from_settings():
    with (patch.object(settings, 'LANGFUSE_ENABLED', True),
          patch.object(settings, 'LANGFUSE_PUBLIC_KEY', 'pk-lf-test'),
          patch.object(settings, 'LANGFUSE_SECRET_KEY', SecretStr('synthetic-secret')),
          patch.object(telemetry, '_client_pid', None), patch.object(telemetry, '_client', None),
          patch.object(telemetry.os, 'getpid', side_effect=[100,100,200]),
          patch('langfuse.Langfuse') as sdk):
        telemetry.get_observability_client()
        telemetry.get_observability_client()
        telemetry.get_observability_client()
        assert sdk.call_count == 2
        assert sdk.call_args.kwargs['secret_key'] == 'synthetic-secret'


def test_all_llm_providers_receive_callback_and_normalization_has_its_own_stage():
    from app.ai import llm_factory
    callback = MagicMock(spec=telemetry.TokenUsageCallback)
    with (patch.object(telemetry, 'llm_callbacks', return_value=[callback]) as callbacks,
          patch.object(llm_factory, 'ChatGroq') as groq,
          patch.object(llm_factory, 'ChatGoogleGenerativeAI') as google,
          patch.object(llm_factory, 'ChatOpenAI') as local):
        for provider in ['groq','google','local']:
            llm_factory._build_llm(provider, 'model', 'http://localhost:9999/v1', 0, stage='normalize')
        assert all(model.call_args.kwargs['callbacks'] == [callback] for model in [groq,google,local])
        assert all(call.args[2] == 'normalize' for call in callbacks.call_args_list)


def test_real_sdk_exports_usage_to_local_otlp_receiver_without_content():
    """Actual SDK/OTLP transport, synthetic data, no Langfuse/cloud account."""
    import gzip
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from langfuse import Langfuse
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
    requests = []
    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = self.rfile.read(int(self.headers['Content-Length']))
            requests.append(gzip.decompress(payload) if self.headers.get('Content-Encoding') == 'gzip' else payload)
            self.send_response(200); self.end_headers(); self.wfile.write(b'')
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Receiver)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    client = Langfuse(public_key='pk-lf-test-' + uuid4().hex, secret_key='synthetic',
                      base_url=f'http://127.0.0.1:{server.server_port}', tracer_provider=TracerProvider(), timeout=2)
    try:
        with telemetry.ai_job('email', uuid4(), 'respond', 2):
            callback = telemetry.TokenUsageCallback(client, 'local', 'test-model', 'respond')
        run = uuid4(); callback.on_chat_model_start({}, ['PRIVATE_STUDENT_BODY'], run_id=run)
        callback.on_llm_end(response({'input_tokens':10,'output_tokens':5,'total_tokens':15}), run_id=run)
        client.flush()
        assert requests and all(b'PRIVATE_STUDENT_BODY' not in request for request in requests)
        records = [ExportTraceServiceRequest.FromString(payload) for payload in requests]
        spans = [span for record in records for resource in record.resource_spans for scope in resource.scope_spans for span in scope.spans]
        assert any(span.name == 'email.respond' for span in spans)
        import json
        usages = [json.loads(attribute.value.string_value) for span in spans for attribute in span.attributes
                  if attribute.key == 'langfuse.observation.usage_details']
        assert {'input':10, 'output':5, 'total':15} in usages
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)

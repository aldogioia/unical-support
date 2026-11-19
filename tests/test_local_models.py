"""Lista dei modelli di un server LLM locale per il menu a tendina delle impostazioni."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.authentication import get_current_user
from app.api.endpoints.ai_settings import router
from app.models.enumerators.enumerators import UserRole
from app.services import local_models_service
from app.services.local_models_service import LocalModelsError, list_local_models


def serve(routes: dict[str, dict]):
    """Server HTTP finto: risponde con il JSON associato al path, 404 altrimenti."""
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = routes.get(self.path)
            self.send_response(200 if body is not None else 404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(body or {}).encode())

        def log_message(self, *args):
            pass

    server = HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f'http://127.0.0.1:{server.server_port}'


@pytest.fixture
def fake_server():
    servers = []

    def start(routes):
        server, url = serve(routes)
        servers.append(server)
        return url
    yield start
    for server in servers:
        server.shutdown()


def test_reads_the_openai_compatible_model_list(fake_server):
    url = fake_server({'/v1/models': {'data': [{'id': 'gemma3:12b'}, {'id': 'kimi-k2'}, {'id': 'gemma3:12b'}]}})
    assert list_local_models(f'{url}/v1/') == ['gemma3:12b', 'kimi-k2']


def test_falls_back_to_the_ollama_tags_endpoint(fake_server):
    url = fake_server({'/api/tags': {'models': [{'name': 'qwen3:8b'}, {'name': 'llama3.2:3b'}]}})
    assert list_local_models(f'{url}/v1') == ['llama3.2:3b', 'qwen3:8b']


def test_unreachable_server_is_reported_with_the_address():
    with pytest.raises(LocalModelsError) as error:
        list_local_models('http://127.0.0.1:9/v1')
    assert '127.0.0.1:9' in str(error.value)


def test_server_without_models_is_an_error(fake_server):
    url = fake_server({'/v1/models': {'data': []}, '/api/tags': {'models': []}})
    with pytest.raises(LocalModelsError):
        list_local_models(f'{url}/v1')


@pytest.mark.parametrize('bad', ['', '   ', 'localhost:11434', 'ftp://host/v1', 'file:///etc/passwd'])
def test_only_http_urls_are_accepted(bad):
    with pytest.raises(LocalModelsError):
        list_local_models(bad)


def client(role):
    app = FastAPI()
    app.include_router(router, prefix='/api/ai-settings')
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4(), role=role)
    return TestClient(app)


def test_endpoint_is_admin_only():
    with patch.object(local_models_service, 'list_local_models') as listing:
        response = client(UserRole.user).get('/api/ai-settings/local-models', params={'base_url': 'http://h:1/v1'})
    assert response.status_code == 403
    listing.assert_not_called()


def test_endpoint_returns_models_and_reports_unreachable_servers():
    with patch.object(local_models_service, 'list_local_models', return_value=['gemma3:12b']):
        ok = client(UserRole.admin).get('/api/ai-settings/local-models', params={'base_url': ' http://h:1/v1 '})
    assert ok.status_code == 200
    assert ok.json() == {'base_url': 'http://h:1/v1', 'models': ['gemma3:12b']}

    with patch.object(local_models_service, 'list_local_models', side_effect=LocalModelsError('Server non raggiungibile')):
        down = client(UserRole.admin).get('/api/ai-settings/local-models', params={'base_url': 'http://h:1/v1'})
    assert down.status_code == 502
    assert 'non raggiungibile' in down.json()['detail']

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.authentication import get_current_user
from app.api.endpoints.emails import router
from app.db.database import get_db
from app.services.email_renderer import LOGO_CID, render_email, render_email_preview


def preview_app(authenticated=True):
    app = FastAPI()
    app.include_router(router, prefix='/api/emails')
    app.dependency_overrides[get_db] = lambda: MagicMock()
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4())
    return TestClient(app)


def test_preview_is_identical_to_delivery_except_for_the_inline_logo():
    text = 'Ciao,\n\nPuoi consultare\nla guida https://example.org/modulo.\n\n- Primo punto\n- Secondo punto'
    html = render_email_preview(text, 'it')
    import re
    restored = re.sub(r'data:image/png;base64,[A-Za-z0-9+/=]+', f'cid:{LOGO_CID}', html)
    assert restored == render_email(text, 'it').html
    assert 'data:image/png;base64,' in html
    assert 'max-width:640px' in html
    assert 'https://example.org/modulo' in html


def test_preview_uses_unsaved_text_and_stored_language_without_saving_or_sending():
    email = SimpleNamespace(response_language='en', ai_disclaimer=None, generated_draft='Original draft')
    with patch('app.services.email_service.get_email', return_value=email), \
         patch('app.services.email_service.update_email_draft') as update, \
         patch('app.listener.gmail_client.GmailClient') as gmail:
        response = preview_app().post(f'/api/emails/{uuid4()}/preview', json={'generated_draft': 'Hello,\n\nEdited <script>unsafe</script>'})
    assert response.status_code == 200
    html = response.json()['html']
    assert '<html lang="en">' in html
    assert 'Edited &lt;script&gt;unsafe&lt;/script&gt;' in html
    assert email.generated_draft == 'Original draft'
    update.assert_not_called()
    gmail.assert_not_called()


@pytest.mark.parametrize('draft', ['', '   '])
def test_empty_preview_is_rejected(draft):
    with patch('app.services.email_service.get_email', return_value=SimpleNamespace(response_language=None, ai_disclaimer=None)):
        response = preview_app().post(f'/api/emails/{uuid4()}/preview', json={'generated_draft': draft})
    assert response.status_code == 422


def test_missing_email_and_unauthenticated_request_are_rejected():
    with patch('app.services.email_service.get_email', return_value=None):
        assert preview_app().post(f'/api/emails/{uuid4()}/preview', json={'generated_draft': 'Ciao'}).status_code == 404
    assert preview_app(False).post(f'/api/emails/{uuid4()}/preview', json={'generated_draft': 'Ciao'}).status_code in (401, 403)

import base64
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.email_formatting import DISCLAIMERS, LEGACY_DISCLAIMERS
from app.services.email_renderer import render_email, LOGO_CID, LOGO_PATH


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.items = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.items.append((tag, dict(attrs)))


def test_renderer_includes_existing_logo_width_and_separate_supervised_notice():
    rendered = render_email('Ciao,\n\nPuoi consultare\nil documento.\n\n- Primo punto\n- Secondo punto', 'it')
    elements = Elements(rendered.html).items
    assert any(tag == 'img' and attrs['src'] == f'cid:{LOGO_CID}' and attrs['alt'] == 'Unical Support' for tag, attrs in elements)
    assert LOGO_PATH.read_bytes().startswith(b'\x89PNG')
    assert 'max-width:640px' in rendered.html
    assert 'max-width:72ch' in rendered.html
    assert 'line-height:1.65' in rendered.html
    assert '#B61918' in rendered.html
    assert '<p style="margin:0 0 20px;">Puoi consultare il documento.</p>' in rendered.html
    assert sum(tag == 'li' for tag, _ in elements) == 2
    assert rendered.plain_text.startswith(DISCLAIMERS['it'])
    assert rendered.html.index('supervisione umana') < rendered.html.index('Ciao,')
    assert rendered.plain_text.count(DISCLAIMERS['it']) == 1


def test_plain_text_html_escape_and_links_are_safe():
    text = 'Ciao <script>alert(1)</script> & benvenuto.\n\nFonte: https://example.org/modulo?a=1&b=2.\n\njavascript:alert(1)\n\n<img src=x onerror=alert(1)>'
    rendered = render_email(text, 'it')
    elements = Elements(rendered.html).items
    assert not any(tag == 'script' for tag, _ in elements)
    assert sum(tag == 'img' for tag, _ in elements) == 1
    anchors = [attrs['href'] for tag, attrs in elements if tag == 'a']
    assert anchors == ['https://example.org/modulo?a=1&b=2']
    assert '&lt;script&gt;' in rendered.html
    assert '<script>' in rendered.plain_text


def test_urls_keep_balanced_parentheses_and_quotes_do_not_inject_attributes():
    rendered = render_email('Vedi (https://example.org/a_(b)). https://example.org/"onclick="evil', 'en')
    anchors = [attrs for tag, attrs in Elements(rendered.html).items if tag == 'a']
    assert anchors[0]['href'] == 'https://example.org/a_(b)'
    assert all(set(attrs) == {'href', 'style'} for attrs in anchors)


def test_legacy_notice_is_rendered_once_in_its_original_language():
    rendered = render_email(LEGACY_DISCLAIMERS['en'] + '\n\nHello,\n\nYou can upload\nyour file.')
    assert rendered.language == 'en'
    assert rendered.plain_text.endswith('Hello,\n\nYou can upload your file.')
    assert rendered.plain_text.startswith(DISCLAIMERS['en'])
    assert LEGACY_DISCLAIMERS['en'] not in rendered.plain_text


def test_stored_custom_translation_and_ordered_list_are_preserved():
    notice = '人工知能の支援により作成し、担当者が送信前に確認しました。'
    rendered = render_email('こんにちは。\n\n3. 最初の項目\n7. 次の項目', 'ja', notice)
    assert rendered.plain_text.startswith(notice)
    assert '<html lang="ja">' in rendered.html
    assert '<ol start="3"' in rendered.html
    assert [attrs['value'] for tag, attrs in Elements(rendered.html).items if tag == 'li'] == ['3', '7']
    with pytest.raises(ValueError):
        render_email('   ')


def test_gmail_builds_multipart_related_logo_and_preserves_thread_headers():
    from app.listener.gmail_client import GmailClient
    client = GmailClient.__new__(GmailClient)
    client.service = MagicMock()
    messages = client.service.users.return_value.messages.return_value
    messages.get.return_value.execute.return_value = {
        'threadId': 'original-thread',
        'payload': {'headers': [
            {'name': 'message-id', 'value': '<original@example.org>'},
            {'name': 'references', 'value': '<earlier@example.org>'},
        ]},
    }
    client.send_reply('gmail-1', 'Hello,\n\nYou can\nupload your file.', 'student@example.org', 're: Documents', 'en')
    request = messages.send.call_args.kwargs
    assert request['body']['threadId'] == 'original-thread'
    parsed = BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(request['body']['raw']))
    assert parsed.get_content_type() == 'multipart/alternative'
    assert parsed['In-Reply-To'] == '<original@example.org>'
    assert parsed['References'] == '<earlier@example.org> <original@example.org>'
    assert parsed['Subject'] == 're: Documents'
    assert parsed['To'] == 'student@example.org'
    assert parsed['Content-Language'] == 'en'
    plain = next(part for part in parsed.walk() if part.get_content_type() == 'text/plain')
    html = next(part for part in parsed.walk() if part.get_content_type() == 'text/html')
    logo = next(part for part in parsed.walk() if part.get_content_type() == 'image/png')
    assert 'You can upload your file.' in plain.get_content()
    assert plain.get_content().strip().startswith(DISCLAIMERS['en'])
    assert f'cid:{LOGO_CID}' in html.get_content()
    assert logo['Content-ID'] == f'<{LOGO_CID}>'
    assert logo.get_content_disposition() == 'inline'
    messages.send.return_value.execute.assert_called_once()


def test_reviewed_draft_is_normalized_and_delivery_metadata_is_forwarded():
    from app.services.email_service import update_email_draft
    from app.schemas.email import EmailUpdateDraft
    from app.models.enumerators.enumerators import EmailStatus
    db = MagicMock()
    email = SimpleNamespace(id=uuid4(), gmail_id='gmail-1', sender='student@example.org', subject='Documents', response_language='en', ai_disclaimer=DISCLAIMERS['en'], status=EmailStatus.DRAFT, draft_revision=0, processing_generation=0, apply_audit_fields=MagicMock())
    db.query.return_value.filter.return_value.populate_existing.return_value.with_for_update.return_value.first.return_value = email
    with patch('app.listener.client_factory.get_email_client') as client:
        result = update_email_draft(db, email.id, EmailUpdateDraft(generated_draft='Hello,\n\nYou can\nupload the file.', status=EmailStatus.SENT), uuid4())
    assert result.generated_draft == 'Hello,\n\nYou can upload the file.'
    client.return_value.__enter__.return_value.send_reply.assert_called_once_with(original_gmail_id='gmail-1', reply_text=result.generated_draft, sender_email='student@example.org', subject='Documents', response_language='en', ai_disclaimer=DISCLAIMERS['en'])

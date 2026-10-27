from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
import imaplib
import smtplib
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from uuid import uuid4
from unittest import TestCase
from unittest.mock import MagicMock, patch

from pydantic import SecretStr, ValidationError

from app.core.config import Settings, settings
from app.listener.client_factory import get_email_client
from app.listener.email_client import EmailClient
from app.listener.smtp_client import ImapSmtpClient
from app.services.email_renderer import LOGO_CID

IMAPError = imaplib.IMAP4.error

def mail_config(**values):
    return settings.model_copy(update={
        'MAIL_PROVIDER': 'smtp', 'MAIL_USERNAME': 'support@example.org',
        'MAIL_PASSWORD': SecretStr('app-password'), **values,
    })


def original_message():
    message = EmailMessage()
    message['From'] = 'Studente è <student@example.org>'
    message['Subject'] = 'Informazioni università'
    message['Message-ID'] = '<original@example.org>'
    message['References'] = '<earlier@example.org>'
    message.set_content('Buongiorno,\nVorrei informazioni.')
    message.add_alternative('<p>Versione HTML</p>', subtype='html')
    message.add_attachment('Un allegato, non il corpo.', filename='notes.txt')
    return message.as_bytes()


class MailFactoryTests(TestCase):
    def test_smtp_selection_never_instantiates_gmail(self):
        import sys
        with patch.dict(sys.modules, {'app.listener.gmail_client': None}):
            client = get_email_client(mail_config())
        self.assertIsInstance(client, EmailClient)
        self.assertIsInstance(client, ImapSmtpClient)

    def test_gmail_remains_available(self):
        with patch('app.listener.gmail_client.GmailClient') as gmail:
            self.assertIs(get_email_client(mail_config(MAIL_PROVIDER='gmail_api')), gmail.return_value)

    def test_missing_password_and_unknown_provider_fail_without_network(self):
        with patch('app.listener.smtp_client.imaplib.IMAP4_SSL') as imap:
            with self.assertRaisesRegex(ValueError, 'MAIL_PASSWORD'):
                get_email_client(mail_config(MAIL_PASSWORD=SecretStr('')))
            with self.assertRaises(ValueError):
                get_email_client(mail_config(MAIL_PROVIDER='unknown'))
        imap.assert_not_called()

    def test_settings_reject_insecure_transport_and_infinite_timeout(self):
        for values in ({'MAIL_SMTP_SECURITY': 'none'}, {'MAIL_IMAP_SECURITY': 'none'},
                       {'MAIL_TIMEOUT_SECONDS': 0}, {'MAIL_FETCH_LIMIT': 0}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                Settings(_env_file=None, _secrets_dir=None, **(settings.model_dump() | values))

    def test_password_loads_from_docker_secret_and_is_masked(self):
        with TemporaryDirectory() as directory:
            Path(directory, 'mail_password').write_text('secret-from-file')
            config = Settings(_env_file=None, _secrets_dir=directory,
                              **settings.model_dump(exclude={'MAIL_PASSWORD'}))
        self.assertEqual(config.MAIL_PASSWORD.get_secret_value(), 'secret-from-file')
        self.assertNotIn('secret-from-file', repr(config))


class ImapSmtpTests(TestCase):
    def setUp(self):
        self.imap = MagicMock()
        self.imap.login.return_value = ('OK', [])
        self.imap.select.return_value = ('OK', [b'2'])
        self.imap.starttls.return_value = ('OK', [])
        self.imap.response.return_value = ('UIDVALIDITY', [b'12345'])
        self.imap.capability.return_value = ('OK', [b'IMAP4rev1 UIDPLUS'])
        self.raw_message = original_message()

        def uid(command, *args):
            if command == 'SEARCH':
                return 'OK', [b'7 19']
            if command == 'FETCH':
                return 'OK', [(b'1 (UID 7 BODY[] {100}', self.raw_message), b')']
            if command == 'STORE':
                return 'OK', []
            raise AssertionError(command)

        self.imap.uid.side_effect = uid
        patcher = patch('app.listener.smtp_client.imaplib.IMAP4_SSL', return_value=self.imap)
        self.ssl_imap = patcher.start()
        self.addCleanup(patcher.stop)
        self.client = ImapSmtpClient(mail_config(MAIL_FETCH_LIMIT=1))
        self.addCleanup(self.client.close)

    def test_intake_decodes_mime_keeps_messages_unread_and_limits_batch(self):
        messages = self.client.fetch_unread_emails()
        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertEqual(message['subject'], 'Informazioni università')
        self.assertIn('Studente è', message['sender'])
        self.assertIn('Vorrei informazioni.', message['body'])
        self.assertNotIn('Un allegato', message['body'])
        self.assertTrue(message['gmail_id'].startswith('imap:'))
        self.imap.uid.assert_any_call('FETCH', b'7', '(BODY.PEEK[] INTERNALDATE)')
        self.assertFalse(any(c.args[0] == 'STORE' for c in self.imap.uid.call_args_list))
        self.assertEqual(self.ssl_imap.call_args.kwargs['timeout'], 30)
        self.assertTrue(self.ssl_imap.call_args.kwargs['ssl_context'].check_hostname)

    def test_only_explicit_mark_as_read_adds_seen_without_expunge(self):
        message = self.client.fetch_unread_emails()[0]
        self.client.mark_as_read(message['gmail_id'])
        self.imap.uid.assert_any_call('STORE', b'7', '+FLAGS.SILENT', '(\\Seen)')
        self.client.close()
        self.imap.logout.assert_called_once()
        self.imap.close.assert_not_called()
        self.imap.expunge.assert_not_called()

    def test_ids_survive_reconnect_and_reject_changed_mailbox_or_validity(self):
        message_id = self.client.fetch_unread_emails()[0]['gmail_id']
        with ImapSmtpClient(mail_config()) as reconnected:
            reconnected.mark_as_read(message_id)
        self.imap.response.return_value = ('UIDVALIDITY', [b'999'])
        with ImapSmtpClient(mail_config()) as changed:
            with self.assertRaisesRegex(ValueError, 'UIDVALIDITY'):
                changed.mark_as_read(message_id)
        with ImapSmtpClient(mail_config(MAIL_USERNAME='other@example.org')) as other:
            with self.assertRaises(ValueError):
                other.mark_as_read(message_id)

    def test_gmail_ids_match_api_and_old_api_ids_resolve_for_marking(self):
        self.imap.capability.return_value = ('OK', [b'IMAP4rev1 X-GM-EXT-1'])
        numeric_id = 1278455344230334865
        self.imap.uid.side_effect = None
        self.imap.uid.return_value = ('OK', [b'7'])
        self.client._connect()
        api_id = self.client._transport_id(b'7', f'1 (UID 7 X-GM-MSGID {numeric_id})'.encode())
        self.assertEqual(api_id, format(numeric_id, 'x'))
        self.client.mark_as_read(api_id)
        self.imap.uid.assert_any_call('SEARCH', None, 'X-GM-MSGID', str(numeric_id))
        self.imap.uid.assert_any_call('STORE', b'7', '+FLAGS.SILENT', '(\\Seen)')

    def test_gmail_fetch_requests_stable_ids_without_setting_seen(self):
        self.imap.capability.return_value = ('OK', [b'X-GM-EXT-1'])
        self.imap.uid.side_effect = [
            ('OK', [b'7']),
            ('OK', [(b'1 (UID 7 X-GM-MSGID 1278455344230334865 BODY[] {100}', self.raw_message)]),
        ]
        message = self.client.fetch_unread_emails()[0]
        self.assertEqual(message['gmail_id'], format(1278455344230334865, 'x'))
        self.imap.uid.assert_any_call('FETCH', b'7', '(BODY.PEEK[] X-GM-MSGID INTERNALDATE)')

    def test_html_only_message_has_readable_text_without_style_or_attachment(self):
        message = EmailMessage()
        message.set_content('<style>.x{color:red}</style><p>Ciao &amp; grazie</p><p>Seconda riga</p>', subtype='html')
        body = self.client._body(message)
        self.assertIn('Ciao & grazie', body)
        self.assertIn('\nSeconda riga', body)
        self.assertNotIn('color:red', body)

    def test_imap_starttls_precedes_login_and_failure_never_sends_password(self):
        with patch('app.listener.smtp_client.imaplib.IMAP4', return_value=self.imap) as factory:
            factory.error = IMAPError
            with ImapSmtpClient(mail_config(MAIL_IMAP_SECURITY='starttls', MAIL_IMAP_PORT=143)) as client:
                client.fetch_unread_emails()
        methods = [c[0] for c in self.imap.method_calls]
        self.assertLess(methods.index('starttls'), methods.index('login'))
        self.imap.reset_mock()
        self.imap.starttls.side_effect = IMAPError('TLS unavailable')
        with patch('app.listener.smtp_client.imaplib.IMAP4', return_value=self.imap) as factory:
            factory.error = IMAPError
            with self.assertRaises(IMAPError):
                ImapSmtpClient(mail_config(MAIL_IMAP_SECURITY='starttls')).fetch_unread_emails()
        self.imap.login.assert_not_called()
        self.imap.shutdown.assert_called_once()

    def test_authentication_and_fetch_failures_are_propagated(self):
        self.imap.login.side_effect = imaplib.IMAP4.error('Authentication failed')
        with self.assertRaises(imaplib.IMAP4.error):
            self.client.fetch_unread_emails()
        self.imap.shutdown.assert_called_once()
        self.imap.login.side_effect = None
        self.imap.uid.side_effect = None
        self.imap.uid.return_value = ('NO', [b'Error'])
        with self.assertRaisesRegex(RuntimeError, 'ricerca non letti'):
            self.client.fetch_unread_emails()

    def test_empty_mailbox_returns_no_messages(self):
        self.imap.uid.side_effect = None
        self.imap.uid.return_value = ('OK', [b''])
        self.assertEqual(self.client.fetch_unread_emails(), [])

    def smtp_server(self):
        server = MagicMock()
        server.__enter__.return_value = server
        server.send_message.return_value = {}
        return server

    def test_smtp_delivery_preserves_thread_rendering_and_envelope(self):
        message_id = self.client.fetch_unread_emails()[0]['gmail_id']
        server = self.smtp_server()
        with patch('app.listener.smtp_client.smtplib.SMTP_SSL', return_value=server) as smtp:
            self.client.send_reply(message_id, 'Hello,\n\nYour reply.', 'Student <student@example.org>', 'Documents', 'en')
        server.login.assert_called_once_with('support@example.org', 'app-password')
        self.assertTrue(smtp.call_args.kwargs['context'].check_hostname)
        self.assertEqual(smtp.call_args.kwargs['timeout'], 30)
        server.starttls.assert_not_called()
        sent = server.send_message.call_args
        self.assertEqual(sent.kwargs, {'from_addr': 'support@example.org', 'to_addrs': ['student@example.org']})
        message = BytesParser(policy=policy.default).parsebytes(sent.args[0].as_bytes())
        self.assertEqual(message['In-Reply-To'], '<original@example.org>')
        self.assertEqual(message['References'], '<earlier@example.org> <original@example.org>')
        self.assertEqual(message['Subject'], 'Re: Documents')
        self.assertEqual(message['Content-Language'], 'en')
        self.assertEqual(message['From'], 'support@example.org')
        self.assertIsNotNone(message['Message-ID'])
        html = next(p for p in message.walk() if p.get_content_type() == 'text/html')
        self.assertIn(f'cid:{LOGO_CID}', html.get_content())
        logo = next(p for p in message.walk() if p.get_content_type() == 'image/png')
        self.assertEqual(logo['Content-ID'], f'<{LOGO_CID}>')
        self.imap.uid.assert_any_call('FETCH', b'7', '(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID REFERENCES)])')

    def test_smtp_starttls_is_mandatory_before_login(self):
        self.client.config = mail_config(MAIL_SMTP_SECURITY='starttls', MAIL_SMTP_PORT=587)
        message_id = self.client.fetch_unread_emails()[0]['gmail_id']
        server = self.smtp_server()
        with patch('app.listener.smtp_client.smtplib.SMTP', return_value=server):
            self.client.send_reply(message_id, 'Reply', 'student@example.org', 'Question')
        methods = [c[0] for c in server.method_calls]
        self.assertLess(methods.index('starttls'), methods.index('login'))
        self.assertEqual(server.ehlo.call_count, 2)
        server.reset_mock()
        server.starttls.side_effect = smtplib.SMTPNotSupportedError('No TLS')
        with patch('app.listener.smtp_client.smtplib.SMTP', return_value=server):
            with self.assertRaises(smtplib.SMTPNotSupportedError):
                self.client.send_reply(message_id, 'Reply', 'student@example.org', 'Question')
        server.login.assert_not_called()
        server.send_message.assert_not_called()

    def test_smtp_rejection_and_missing_original_do_not_report_success(self):
        message_id = self.client.fetch_unread_emails()[0]['gmail_id']
        server = self.smtp_server()
        server.send_message.return_value = {'student@example.org': (550, b'Rejected')}
        with patch('app.listener.smtp_client.smtplib.SMTP_SSL', return_value=server):
            with self.assertRaisesRegex(RuntimeError, 'rifiutato'):
                self.client.send_reply(message_id, 'Reply', 'student@example.org', 'Question')
        self.imap.uid.side_effect = None
        self.imap.uid.return_value = ('OK', [None])
        with patch('app.listener.smtp_client.smtplib.SMTP_SSL') as smtp:
            with self.assertRaisesRegex(RuntimeError, 'originale non disponibile'):
                self.client.send_reply(message_id, 'Reply', 'student@example.org', 'Question')
        smtp.assert_not_called()

    def test_reviewed_draft_uses_selected_smtp_provider_and_retains_failed_draft(self):
        from app.models.enumerators.enumerators import EmailStatus
        from app.schemas.email import EmailUpdateDraft
        from app.services.email_service import update_email_draft

        message_id = self.client.fetch_unread_emails()[0]['gmail_id']
        for rejected in (False, True):
            with self.subTest(rejected=rejected):
                email = SimpleNamespace(
                    id=uuid4(), gmail_id=message_id, sender='student@example.org',
                    subject='Documents', response_language='en', ai_disclaimer=None,
                    status=EmailStatus.DRAFT, draft_revision=0, processing_generation=0, apply_audit_fields=MagicMock(),
                )
                db = MagicMock()
                db.query.return_value.filter.return_value.populate_existing.return_value.with_for_update.return_value.first.return_value = email
                server = self.smtp_server()
                if rejected:
                    server.login.side_effect = smtplib.SMTPAuthenticationError(535, b'Bad credentials')
                with patch('app.listener.client_factory.settings', mail_config()), \
                     patch('app.listener.smtp_client.smtplib.SMTP_SSL', return_value=server):
                    result = update_email_draft(
                        db, email.id,
                        EmailUpdateDraft(generated_draft='Hello,\n\nYour\nreply.', status=EmailStatus.SENT),
                        uuid4(),
                    )
                self.assertEqual(result.status, EmailStatus.FAILED if rejected else EmailStatus.SENT)
                self.assertEqual(result.generated_draft, 'Hello,\n\nYour reply.')
                self.assertEqual(server.send_message.call_count, 0 if rejected else 1)
                db.commit.assert_called_once()

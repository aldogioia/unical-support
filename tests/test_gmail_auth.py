from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import MagicMock, patch

from app.listener.gmail_client import GmailClient


class GmailAuthTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp_path = Path(directory.name)

    def test_reauth_replaces_unusable_token_and_supports_docker_callback(self):
        tmp_path = self.tmp_path
        token_path = tmp_path / 'token.json'
        token_path.write_text('unusable previous token')
        credentials = MagicMock()
        credentials.to_json.return_value = '{"token": "new"}'
        with patch('app.listener.gmail_client.Credentials.from_authorized_user_file') as load, \
             patch('app.listener.gmail_client.InstalledAppFlow.from_client_secrets_file') as flow, \
             patch('app.listener.gmail_client.build'):
            flow.return_value.run_local_server.return_value = credentials
            GmailClient(token_path=str(token_path), force_reauth=True,
                        auth_port=8080, open_browser=False, bind_addr='0.0.0.0')

        load.assert_not_called()
        flow.return_value.run_local_server.assert_called_once_with(
            host='localhost', bind_addr='0.0.0.0', port=8080,
            open_browser=False, prompt='consent',
        )
        assert token_path.read_text() == '{"token": "new"}'


    def test_failed_reauth_preserves_previous_token(self):
        tmp_path = self.tmp_path
        token_path = tmp_path / 'token.json'
        token_path.write_text('previous token')
        with patch('app.listener.gmail_client.InstalledAppFlow.from_client_secrets_file') as flow:
            flow.return_value.run_local_server.side_effect = RuntimeError('Consent failed')
            with self.assertRaisesRegex(RuntimeError, 'Consent failed'):
                GmailClient(token_path=str(token_path), force_reauth=True)
        assert token_path.read_text() == 'previous token'


    def test_normal_auth_reuses_saved_credentials(self):
        self.check_saved_credentials(expired=False)

    def test_normal_auth_refreshes_saved_credentials(self):
        self.check_saved_credentials(expired=True)

    def check_saved_credentials(self, expired):
        tmp_path = self.tmp_path
        token_path = tmp_path / 'token.json'
        token_path.write_text('saved token')
        credentials = MagicMock(valid=not expired, expired=expired, refresh_token='refresh')
        credentials.to_json.return_value = 'refreshed token'
        with patch('app.listener.gmail_client.Credentials.from_authorized_user_file', return_value=credentials), \
             patch('app.listener.gmail_client.InstalledAppFlow.from_client_secrets_file') as flow, \
             patch('app.listener.gmail_client.Request'), \
             patch('app.listener.gmail_client.build'):
            GmailClient(token_path=str(token_path))

        flow.assert_not_called()
        assert credentials.refresh.call_count == int(expired)
        assert token_path.read_text() == ('refreshed token' if expired else 'saved token')

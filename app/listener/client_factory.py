"""Select a transport without importing or authenticating unused providers."""
from app.core.config import settings
from app.listener.email_client import EmailClient


def get_email_client(config=None) -> EmailClient:
    config = settings if config is None else config
    if config.MAIL_PROVIDER == 'gmail_api':
        from app.listener.gmail_client import GmailClient
        return GmailClient()
    if config.MAIL_PROVIDER == 'smtp':
        from app.listener.smtp_client import ImapSmtpClient
        return ImapSmtpClient(config)
    raise ValueError('MAIL_PROVIDER deve essere gmail_api oppure smtp.')

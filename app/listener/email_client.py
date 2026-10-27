"""Transport contract shared by Gmail API and IMAP/SMTP providers."""
from abc import ABC, abstractmethod


class EmailClient(ABC):
    @abstractmethod
    def fetch_unread_emails(self) -> list[dict]:
        """Return unread messages without marking them as read.

        ``gmail_id`` is the historical database field for a transport message ID.
        """

    @abstractmethod
    def mark_as_read(self, msg_id: str):
        """Mark a successfully imported message as read."""

    @abstractmethod
    def send_reply(self, original_gmail_id: str, reply_text: str,
                   sender_email: str, subject: str,
                   response_language: str | None = None,
                   ai_disclaimer: str | None = None):
        """Reply using the original Message-ID and References headers."""

    def close(self):
        """Release transport connections, if any."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


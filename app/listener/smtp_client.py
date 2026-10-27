"""Password-based mail transport: IMAP for intake, SMTP for delivery."""
from contextlib import suppress
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from hashlib import sha256
from html.parser import HTMLParser
import imaplib
import re
import smtplib
import ssl

from app.listener.email_client import EmailClient
from app.listener.message_builder import build_reply_message


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if not self.hidden and tag in ('br', 'p', 'div', 'li', 'tr'):
            self.chunks.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if not self.hidden and tag in ('p', 'div', 'li', 'tr'):
            self.chunks.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.chunks.append(data)


class ImapSmtpClient(EmailClient):
    def __init__(self, config):
        self.config = config
        if not config.MAIL_USERNAME or not config.MAIL_PASSWORD.get_secret_value():
            raise ValueError('Configura MAIL_USERNAME e MAIL_PASSWORD per il provider smtp.')
        if not config.MAIL_IMAP_HOST or not config.MAIL_SMTP_HOST:
            raise ValueError('Configura MAIL_IMAP_HOST e MAIL_SMTP_HOST.')
        self._imap = None
        self._uidvalidity = None
        self._gmail = False
        identity = '\0'.join((config.MAIL_IMAP_HOST.lower(), str(config.MAIL_IMAP_PORT),
                              config.MAIL_USERNAME, config.MAIL_IMAP_FOLDER))
        self._mailbox_tag = sha256(identity.encode()).hexdigest()[:24]

    @staticmethod
    def _check(result, operation):
        status, data = result
        if status != 'OK':
            raise RuntimeError(f'Operazione IMAP fallita: {operation}.')
        return data

    def _connect(self):
        if self._imap is not None:
            return self._imap
        config = self.config
        context = ssl.create_default_context()
        if config.MAIL_IMAP_SECURITY == 'ssl':
            connection = imaplib.IMAP4_SSL(config.MAIL_IMAP_HOST, config.MAIL_IMAP_PORT,
                                         ssl_context=context, timeout=config.MAIL_TIMEOUT_SECONDS)
        else:
            connection = imaplib.IMAP4(config.MAIL_IMAP_HOST, config.MAIL_IMAP_PORT,
                                     timeout=config.MAIL_TIMEOUT_SECONDS)
        try:
            if config.MAIL_IMAP_SECURITY == 'starttls':
                self._check(connection.starttls(ssl_context=context), 'STARTTLS')
            self._check(connection.login(config.MAIL_USERNAME, config.MAIL_PASSWORD.get_secret_value()), 'login')
            mailbox = '"' + config.MAIL_IMAP_FOLDER.replace('\\', '\\\\').replace('"', '\\"') + '"'
            self._check(connection.select(mailbox), 'selezione cartella')
            _, validity = connection.response('UIDVALIDITY')
            if not validity or not validity[0] or not validity[0].isdigit():
                raise RuntimeError('Il server IMAP non ha fornito UIDVALIDITY.')
            self._uidvalidity = validity[0].decode('ascii')
            capabilities = self._check(connection.capability(), 'capability')
            self._gmail = b'X-GM-EXT-1' in b' '.join(capabilities).upper().split()
        except BaseException:
            with suppress(OSError, imaplib.IMAP4.error):
                connection.shutdown()
            raise
        self._imap = connection
        return connection

    def close(self):
        if self._imap is not None:
            connection, self._imap = self._imap, None
            # Do not CLOSE the mailbox: that could expunge unrelated deleted mail.
            try:
                connection.logout()
            except (OSError, imaplib.IMAP4.error):
                with suppress(OSError, imaplib.IMAP4.error):
                    connection.shutdown()

    def _fetch(self, uid: bytes, fields: str):
        data = self._check(self._connect().uid('FETCH', uid, fields), 'lettura messaggio')
        for part in data:
            if isinstance(part, tuple) and len(part) >= 2 and isinstance(part[1], bytes):
                return part[0], BytesParser(policy=policy.default).parsebytes(part[1])
        raise RuntimeError('Messaggio originale non disponibile sul server IMAP.')

    def _transport_id(self, uid: bytes, metadata: bytes):
        if self._gmail:
            match = re.search(rb'X-GM-MSGID\s+(\d+)', metadata, re.IGNORECASE)
            if not match:
                raise RuntimeError('Identificativo Gmail non disponibile nella risposta IMAP.')
            # Gmail API uses the hexadecimal form of IMAP's decimal X-GM-MSGID.
            return format(int(match[1]), 'x')
        return f'imap:{self._mailbox_tag}:{self._uidvalidity}:{uid.decode("ascii")}'

    def _resolve_uid(self, msg_id: str) -> bytes:
        connection = self._connect()
        if msg_id.startswith('imap:'):
            parts = msg_id.split(':')
            if (len(parts) != 4 or parts[1] != self._mailbox_tag
                    or parts[2] != self._uidvalidity or not parts[3].isdigit()):
                raise ValueError('Il messaggio appartiene a una cartella, casella o UIDVALIDITY diversa.')
            return parts[3].encode('ascii')
        if self._gmail and re.fullmatch(r'[0-9a-fA-F]+', msg_id):
            data = self._check(connection.uid('SEARCH', None, 'X-GM-MSGID', str(int(msg_id, 16))),
                               'ricerca messaggio Gmail')
            matches = data[0].split() if data and data[0] else []
            if len(matches) == 1:
                return matches[0]
        raise ValueError('Messaggio originale non trovato nella cartella IMAP configurata.')

    @staticmethod
    def _body(message):
        part = message.get_body(preferencelist=('plain', 'html'))
        if part is None:
            return 'Nessun testo estratto.'
        try:
            text = part.get_content()
        except (LookupError, UnicodeError):
            text = (part.get_payload(decode=True) or b'').decode('utf-8', errors='replace')
        if part.get_content_type() == 'text/html':
            parser = _HTMLText()
            parser.feed(text)
            text = ''.join(parser.chunks)
        return text.strip() or 'Nessun testo estratto.'

    def fetch_unread_emails(self) -> list[dict]:
        connection = self._connect()
        data = self._check(connection.uid('SEARCH', None, 'UNSEEN'), 'ricerca non letti')
        uids = data[0].split() if data and data[0] else []
        messages = []
        fields = '(BODY.PEEK[] X-GM-MSGID)' if self._gmail else '(BODY.PEEK[])'
        for uid in uids[:self.config.MAIL_FETCH_LIMIT]:
            metadata, message = self._fetch(uid, fields)
            messages.append({
                'gmail_id': self._transport_id(uid, metadata),
                'sender': str(message.get('From', 'Sconosciuto')),
                'subject': str(message.get('Subject', 'Nessun Oggetto')),
                'body': self._body(message),
            })
        return messages

    def mark_as_read(self, msg_id: str):
        uid = self._resolve_uid(msg_id)
        self._check(self._connect().uid('STORE', uid, '+FLAGS.SILENT', '(\\Seen)'), 'segna come letto')

    def send_reply(self, original_gmail_id: str, reply_text: str, sender_email: str,
                   subject: str, response_language: str | None = None,
                   ai_disclaimer: str | None = None):
        uid = self._resolve_uid(original_gmail_id)
        _, original = self._fetch(uid, '(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID REFERENCES)])')
        config = self.config
        from_address = config.MAIL_FROM or config.MAIL_USERNAME
        msg = build_reply_message(
            reply_text, sender_email, subject, response_language, ai_disclaimer,
            message_id=original.get('Message-ID'), references=str(original.get('References', '')),
            from_address=from_address,
        )
        recipient = parseaddr(sender_email)[1]
        if not recipient:
            raise ValueError('Indirizzo del destinatario non valido.')
        context = ssl.create_default_context()
        if config.MAIL_SMTP_SECURITY == 'ssl':
            server = smtplib.SMTP_SSL(config.MAIL_SMTP_HOST, config.MAIL_SMTP_PORT,
                                     context=context, timeout=config.MAIL_TIMEOUT_SECONDS)
        else:
            server = smtplib.SMTP(config.MAIL_SMTP_HOST, config.MAIL_SMTP_PORT,
                                 timeout=config.MAIL_TIMEOUT_SECONDS)
        with server:
            if config.MAIL_SMTP_SECURITY == 'starttls':
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
            server.login(config.MAIL_USERNAME, config.MAIL_PASSWORD.get_secret_value())
            refused = server.send_message(msg, from_addr=parseaddr(from_address)[1], to_addrs=[recipient])
            if refused:
                raise RuntimeError('Il server SMTP ha rifiutato il destinatario.')

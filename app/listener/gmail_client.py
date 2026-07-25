import os.path
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.text import MIMEText

SCOPES = ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/gmail.send']

class GmailClient:
    def __init__(self, credentials_path="credentials.json", token_path="token.json"):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = self._authenticate()

    def _authenticate(self):
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())

        return build('gmail', 'v1', credentials=creds)

    def fetch_unread_emails(self):
        """Cerca email non lette, estrae i dati e restituisce una lista di dizionari."""
        results = self.service.users().messages().list(userId='me', q='is:unread').execute()
        messages = results.get('messages', [])
        
        emails_data = []
        for msg in messages:
            msg_id = msg['id']

            message_detail = self.service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            payload = message_detail.get('payload', {})
            headers = payload.get('headers', [])

            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "Nessun Oggetto")
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "Sconosciuto")

            body = self._extract_body(payload)

            emails_data.append({
                "gmail_id": msg_id,
                "sender": sender,
                "subject": subject,
                "body": body
            })

        return emails_data

    def _extract_body(self, payload):
        """Funzione ricorsiva per estrarre il testo da payload complessi/multipart"""
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        return base64.urlsafe_b64decode(data).decode('utf-8')
                elif 'parts' in part:
                    return self._extract_body(part)
        elif 'body' in payload and 'data' in payload['body']:
            data = payload['body']['data']
            return base64.urlsafe_b64decode(data).decode('utf-8')
        return "Nessun testo estratto."

    def mark_as_read(self, msg_id):
        """Rimuove l'etichetta UNREAD da Gmail in modo da non ripescarla al ciclo successivo."""
        self.service.users().messages().modify(
            userId='me', 
            id=msg_id, 
            body={'removeLabelIds': ['UNREAD']}
        ).execute()

    def send_reply(self, original_gmail_id: str, reply_text: str, sender_email: str, subject: str):
        """Invia una risposta all'email originale mantenendo il thread Gmail."""

        # Recupera il thread ID e il Message-ID originale per il threading corretto
        original = self.service.users().messages().get(
            userId='me', id=original_gmail_id, format='metadata',
            metadataHeaders=['From', 'Subject', 'Message-ID']
        ).execute()

        headers = original.get('payload', {}).get('headers', [])
        message_id = next((h['value'] for h in headers if h['name'] == 'Message-ID'), None)
        thread_id = original.get('threadId')

        # Costruisce l'email di risposta
        msg = MIMEText(reply_text, 'plain', 'utf-8')
        msg['To'] = sender_email
        msg['Subject'] = f"Re: {subject}" if not subject.startswith('Re:') else subject
        if message_id:
            msg['In-Reply-To'] = message_id
            msg['References'] = message_id

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')

        self.service.users().messages().send(
            userId='me',
            body={'raw': raw, 'threadId': thread_id}
        ).execute()

# Per rinnovare il token di testing
#GmailClient()
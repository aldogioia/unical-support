import os.path
import base64
import argparse
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from app.services.email_renderer import render_email, LOGO_PATH, LOGO_CID

SCOPES = ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/gmail.send']

class GmailClient:
    def __init__(self, credentials_path="credentials.json", token_path="token.json", *,
                 force_reauth=False, auth_port=0, open_browser=True, bind_addr=None):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = self._authenticate(
            force_reauth=force_reauth, auth_port=auth_port,
            open_browser=open_browser, bind_addr=bind_addr,
        )

    def _authenticate(self, *, force_reauth=False, auth_port=0, open_browser=True, bind_addr=None):
        creds = None
        if not force_reauth and os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(
                    host='localhost', bind_addr=bind_addr, port=auth_port,
                    open_browser=open_browser, prompt='consent',
                )
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

    def send_reply(self, original_gmail_id: str, reply_text: str, sender_email: str, subject: str, response_language: str | None = None, ai_disclaimer: str | None = None):
        """Invia una risposta all'email originale mantenendo il thread Gmail."""

        # Recupera il thread ID e il Message-ID originale per il threading corretto
        original = self.service.users().messages().get(
            userId='me', id=original_gmail_id, format='metadata',
            metadataHeaders=['From', 'Subject', 'Message-ID', 'References']
        ).execute()

        headers = original.get('payload', {}).get('headers', [])
        original_headers = {h['name'].lower(): h['value'] for h in headers}
        message_id = original_headers.get('message-id')
        thread_id = original.get('threadId')

        # Costruisce l'email di risposta
        rendered = render_email(reply_text, response_language, ai_disclaimer)
        msg = MIMEMultipart('alternative')
        msg.attach(MIMEText(rendered.plain_text, 'plain', 'utf-8'))
        html_part = MIMEMultipart('related')
        html_part.attach(MIMEText(rendered.html, 'html', 'utf-8'))
        logo = MIMEImage(LOGO_PATH.read_bytes(), _subtype='png')
        logo.add_header('Content-ID', f'<{LOGO_CID}>')
        logo.add_header('Content-Disposition', 'inline', filename='unical-logo.png')
        html_part.attach(logo)
        msg.attach(html_part)
        msg['Content-Language'] = rendered.language
        msg['To'] = sender_email
        msg['Subject'] = f"Re: {subject}" if not subject.lower().startswith('re:') else subject
        references = original_headers.get('references', '').strip()
        if message_id:
            msg['In-Reply-To'] = message_id
            if message_id not in references.split():
                references = f'{references} {message_id}'.strip()
        if references:
            msg['References'] = references

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')

        self.service.users().messages().send(
            userId='me',
            body={'raw': raw, 'threadId': thread_id}
        ).execute()

def main():
    parser = argparse.ArgumentParser(description='Autorizza o rinnova il token Gmail.')
    parser.add_argument('--reauth', action='store_true', help='Ignora il token esistente e richiedi un nuovo consenso.')
    parser.add_argument('--port', type=int, default=0, help='Porta del callback OAuth (0: automatica).')
    parser.add_argument('--bind-address', default=None, help='Indirizzo di ascolto del callback (Docker: 0.0.0.0).')
    parser.add_argument('--no-browser', action='store_true', help='Stampa il link da aprire nel browser del computer.')
    args = parser.parse_args()
    GmailClient(
        force_reauth=args.reauth, auth_port=args.port,
        open_browser=not args.no_browser, bind_addr=args.bind_address,
    )
    print('Autenticazione Gmail completata: token.json salvato e pronto per l\'uso.')


if __name__ == '__main__':
    main()

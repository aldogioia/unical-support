"""Identical MIME rendering and reply headers for every mail transport."""
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

from app.services.email_renderer import render_email, LOGO_PATH, LOGO_CID


def build_reply_message(reply_text: str, recipient: str, subject: str,
                        response_language: str | None = None,
                        ai_disclaimer: str | None = None, *,
                        message_id: str | None = None, references: str = '',
                        from_address: str | None = None) -> MIMEMultipart:
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
    msg['To'] = recipient
    msg['Subject'] = f'Re: {subject}' if not subject.lower().startswith('re:') else subject
    msg['Date'] = formatdate(localtime=False)
    msg['Message-ID'] = make_msgid()
    if from_address:
        msg['From'] = from_address
    references = references.strip()
    if message_id:
        msg['In-Reply-To'] = message_id
        if message_id not in references.split():
            references = f'{references} {message_id}'.strip()
    if references:
        msg['References'] = references
    return msg


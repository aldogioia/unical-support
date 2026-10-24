"""Safe, email-client-friendly rendering of operator-approved plain text."""
from dataclasses import dataclass
from html import escape
from pathlib import Path
import re

from app.core.email_formatting import (
    LIST_ITEM, extract_disclaimer, get_ai_disclaimer, normalize_language,
)

LOGO_PATH = Path(__file__).resolve().parents[1] / 'assets' / 'unical-logo.png'
LOGO_CID = 'unical-support-logo'
URL = re.compile(r'https?://[^\s<>]+', re.IGNORECASE)
LABELS = {
    'it': ('Segreteria studenti', 'Intelligenza artificiale, supervisione umana'),
    'en': ('Student services', 'AI assistance, human review'),
    'es': ('Atención al estudiante', 'Inteligencia artificial, supervisión humana'),
    'fr': ('Services aux étudiants', 'Intelligence artificielle, supervision humaine'),
    'de': ('Studierendenservice', 'KI-Unterstützung, menschliche Prüfung'),
    'pt': ('Serviços aos estudantes', 'Inteligência artificial, supervisão humana'),
}


@dataclass(frozen=True)
class RenderedEmail:
    plain_text: str
    html: str
    language: str


def _linkify(text: str) -> str:
    """Escape all prose; only HTTP(S) URLs become anchors."""
    result = []
    cursor = 0
    for match in URL.finditer(text):
        url = match.group().rstrip('.,;:!?')
        for opening, closing in [('(', ')'), ('[', ']'), ('{', '}')]:
            while url.endswith(closing) and url.count(closing) > url.count(opening):
                url = url[:-1]
        result.append(escape(text[cursor:match.start()]))
        safe_url = escape(url, quote=True)
        result.append(f'<a href="{safe_url}" style="color:#B61918;text-decoration:underline;overflow-wrap:anywhere;word-break:break-word;">{escape(url)}</a>')
        cursor = match.start() + len(url)
    result.append(escape(text[cursor:]))
    return ''.join(result)


def _render_body(body: str) -> str:
    parts = []
    for block in body.split('\n\n'):
        if not LIST_ITEM.match(block):
            parts.append(f'<p style="margin:0 0 20px;">{_linkify(block)}</p>')
            continue
        kind = None
        for line in block.splitlines():
            next_kind = 'ol' if re.match(r'^\d+[.)]\s+', line) else 'ul'
            if next_kind != kind:
                if kind:
                    parts.append(f'</{kind}>')
                start = ''
                if next_kind == 'ol':
                    start = f' start="{int(re.match(r"^\d+", line).group())}"'
                parts.append(f'<{next_kind}{start} style="margin:0 0 20px;padding-left:24px;">')
                kind = next_kind
            content = LIST_ITEM.sub('', line, count=1)
            number = f' value="{int(re.match(r"^\d+", line).group())}"' if next_kind == 'ol' else ''
            parts.append(f'<li{number} style="padding-left:4px;margin:0 0 8px;">{_linkify(content)}</li>')
        if kind:
            parts.append(f'</{kind}>')
    return ''.join(parts)


def render_email(reply_text: str, response_language: str | None = None, ai_disclaimer: str | None = None) -> RenderedEmail:
    body, inferred_language = extract_disclaimer(reply_text, ai_disclaimer)
    if not body:
        raise ValueError('La risposta non può essere vuota.')
    language = normalize_language(response_language or inferred_language)
    disclaimer = get_ai_disclaimer(language, ai_disclaimer)
    subtitle, notice_title = LABELS.get(language, ('', 'AI'))
    html_body = _render_body(body)
    html = f'''<!doctype html>
<html lang="{escape(language, quote=True)}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>Unical Support</title>
<style>@media only screen and (max-width:600px){{.email-shell{{padding:12px 8px!important;}}.email-padding{{padding:24px 20px!important;}}.email-notice{{padding-bottom:0!important;}}}}</style></head>
<body style="margin:0;padding:0;background-color:#f5f5f4;color:#242424;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f5f5f4;"><tr><td align="center" class="email-shell" style="padding:32px 12px;">
<!--[if mso]><table role="presentation" width="640" cellpadding="0" cellspacing="0"><tr><td><![endif]-->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:640px;background-color:#ffffff;border:1px solid #e5e5e5;border-top:4px solid #B61918;border-radius:4px;">
<tr><td class="email-padding" style="padding:28px 32px;border-bottom:1px solid #eeeeed;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr><td width="44" style="width:44px;vertical-align:middle;"><img src="cid:{LOGO_CID}" alt="Unical Support" width="40" height="40" style="display:block;width:40px;height:40px;border:0;"></td>
<td style="padding-left:14px;font-family:Arial,Helvetica,sans-serif;vertical-align:middle;"><div style="font-size:20px;line-height:26px;font-weight:700;letter-spacing:-0.3px;color:#242424;">Unical Support</div><div style="font-size:12px;line-height:18px;color:#737373;">{escape(subtitle)}</div></td></tr></table>
</td></tr>
<tr><td class="email-padding email-notice" style="padding:24px 32px 0;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f4f4f3;border:1px solid #e8e8e6;border-radius:4px;"><tr><td style="padding:12px 14px;font-family:Arial,Helvetica,sans-serif;font-size:11px;line-height:17px;font-style:italic;color:#777777;">
<p style="margin:0 0 4px;font-size:11px;line-height:17px;font-weight:400;font-style:italic;color:#777777;">{escape(notice_title)}</p>
<p style="margin:0;font-size:11px;line-height:17px;font-style:italic;color:#777777;">{escape(disclaimer)}</p>
</td></tr></table>
</td></tr>
<tr><td class="email-padding" style="padding:32px;font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.65;mso-line-height-rule:at-least;letter-spacing:normal;color:#242424;overflow-wrap:anywhere;word-wrap:break-word;">
<div style="max-width:72ch;">{html_body}</div>
</td></tr>
</table>
<!--[if mso]></td></tr></table><![endif]-->
</td></tr></table></body></html>'''
    return RenderedEmail(plain_text=f'{disclaimer}\n\n{body}', html=html, language=language)


def render_email_preview(reply_text: str, response_language: str | None = None, ai_disclaimer: str | None = None) -> str:
    """Render the delivery HTML with an embedded logo for a sandboxed preview."""
    import base64
    rendered = render_email(reply_text, response_language, ai_disclaimer)
    logo = base64.b64encode(LOGO_PATH.read_bytes()).decode('ascii')
    return rendered.html.replace(f'cid:{LOGO_CID}', f'data:image/png;base64,{logo}')

import re

from app.core.config import settings

LEGACY_DISCLAIMERS = {
    "it": "Questa risposta è stata generata con l'intelligenza artificiale e potrebbe contenere errori. Verifica le informazioni nelle fonti indicate.",
    "en": "This reply was generated using artificial intelligence and may contain errors. Please verify the information in the cited sources.",
    "es": "Esta respuesta se ha generado con inteligencia artificial y puede contener errores. Comprueba la información en las fuentes indicadas.",
    "fr": "Cette réponse a été générée à l'aide de l'intelligence artificielle et peut contenir des erreurs. Vérifiez les informations dans les sources citées.",
    "de": "Diese Antwort wurde mit künstlicher Intelligenz erstellt und kann Fehler enthalten. Bitte überprüfen Sie die Informationen anhand der angegebenen Quellen.",
    "pt": "Esta resposta foi gerada com inteligência artificial e pode conter erros. Verifique as informações nas fontes indicadas.",
}

DISCLAIMERS = {
    "it": "Questa risposta è stata preparata con l'ausilio dell'intelligenza artificiale e revisionata da un operatore prima dell'invio. L'IA può commettere errori: verifica le informazioni nelle fonti indicate.",
    "en": "This reply was prepared with the assistance of artificial intelligence and reviewed by a staff member before sending. AI can make mistakes: please verify the information in the cited sources.",
    "es": "Esta respuesta se ha preparado con ayuda de la inteligencia artificial y ha sido revisada por un miembro del personal antes del envío. La IA puede cometer errores: comprueba la información en las fuentes indicadas.",
    "fr": "Cette réponse a été préparée avec l'aide de l'intelligence artificielle et relue par un membre du personnel avant l'envoi. L'IA peut commettre des erreurs : vérifiez les informations dans les sources citées.",
    "de": "Diese Antwort wurde mithilfe künstlicher Intelligenz erstellt und vor dem Versand von einem Mitarbeitenden geprüft. KI kann Fehler machen: Bitte überprüfen Sie die Informationen anhand der angegebenen Quellen.",
    "pt": "Esta resposta foi preparada com o auxílio da inteligência artificial e revista por um membro da equipa antes do envio. A IA pode cometer erros: verifique as informações nas fontes indicadas.",
}


def normalize_language(language: str | None) -> str:
    language = (language or '').strip() or settings.AI_RESPONSE_FALLBACK_LANGUAGE
    return language.strip().lower().replace('_', '-').split('-')[0]


def response_language_for(detected_language: str | None) -> str:
    language = normalize_language(detected_language)
    return language


LIST_ITEM = re.compile(r"^(?:[-*•]\s+|\d+[.)]\s+)")


def normalize_email_text(text: str) -> str:
    """Remove hard wraps while retaining paragraphs and individual list items."""
    text = text.replace('\r\n', '\n').replace('\r', '\n').strip()
    blocks = []
    for block in re.split(r'\n[ \t]*\n+', text):
        groups = []
        lines = []
        in_list = False
        for raw_line in block.splitlines():
            line = re.sub(r'[ \t]+', ' ', raw_line.strip())
            if not line:
                continue
            if LIST_ITEM.match(line):
                if lines and not in_list:
                    groups.append(' '.join(lines))
                    lines = []
                lines.append(line)
                in_list = True
            elif in_list:
                lines[-1] += ' ' + line
            else:
                lines.append(line)
        if lines:
            groups.append(('\n' if in_list else ' ').join(lines))
        blocks.extend(groups)
    return '\n\n'.join(blocks)


def extract_disclaimer(text: str, extra: str | None = None) -> tuple[str, str | None]:
    """Remove known boundary notices from legacy drafts; infer their language."""
    body = normalize_email_text(text)
    inferred = None
    notices = {normalize_email_text(notice): code
               for translations in (LEGACY_DISCLAIMERS, DISCLAIMERS, settings.AI_DISCLAIMER_TRANSLATIONS)
               for code, notice in translations.items() if notice.strip()}
    if extra and extra.strip():
        notices[normalize_email_text(extra)] = None
    changed = True
    while changed:
        changed = False
        for notice, code in notices.items():
            for at_start in (True, False):
                if (body == notice or (at_start and body.startswith(notice + '\n\n'))
                        or (not at_start and body.endswith('\n\n' + notice))):
                    body = (body[len(notice):] if at_start else body[:-len(notice)]).strip()
                    inferred = inferred or code
                    changed = True
                    break
            if changed:
                break
    return body, inferred


def get_ai_disclaimer(response_language: str | None = None, ai_disclaimer: str | None = None) -> str:
    language = normalize_language(response_language)
    disclaimer = ({**DISCLAIMERS, **settings.AI_DISCLAIMER_TRANSLATIONS}.get(language)
                  or (ai_disclaimer or '').strip())
    if not disclaimer:
        raise ValueError("Fornisci ai_disclaimer tradotto nella lingua della risposta e riprova a salvare la bozza.")
    normalized = normalize_email_text(disclaimer)
    if not normalized:
        raise ValueError('La nota di trasparenza IA non può essere vuota.')
    return normalized


def prepare_draft(draft_text: str, response_language: str | None = None, ai_disclaimer: str | None = None) -> str:
    """Store only the normalized answer. The supervised notice is rendered at send time."""
    language = response_language_for(response_language)
    get_ai_disclaimer(language, ai_disclaimer)
    body, _ = extract_disclaimer(draft_text, ai_disclaimer)
    if not body:
        raise ValueError("La bozza deve contenere una risposta oltre al disclaimer.")
    return body

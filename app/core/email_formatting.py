from app.core.config import settings

DISCLAIMERS = {
    "it": "Questa risposta è stata generata con l'intelligenza artificiale e potrebbe contenere errori. Verifica le informazioni nelle fonti indicate.",
    "en": "This reply was generated using artificial intelligence and may contain errors. Please verify the information in the cited sources.",
    "es": "Esta respuesta se ha generado con inteligencia artificial y puede contener errores. Comprueba la información en las fuentes indicadas.",
    "fr": "Cette réponse a été générée à l'aide de l'intelligence artificielle et peut contenir des erreurs. Vérifiez les informations dans les sources citées.",
    "de": "Diese Antwort wurde mit künstlicher Intelligenz erstellt und kann Fehler enthalten. Bitte überprüfen Sie die Informationen anhand der angegebenen Quellen.",
    "pt": "Esta resposta foi gerada com inteligência artificial e pode conter erros. Verifique as informações nas fontes indicadas.",
}


def normalize_language(language: str | None) -> str:
    language = (language or '').strip() or settings.AI_RESPONSE_FALLBACK_LANGUAGE
    return language.strip().lower().replace('_', '-').split('-')[0]


def response_language_for(detected_language: str | None) -> str:
    language = normalize_language(detected_language)
    overrides = settings.AI_RESPONSE_LANGUAGE_OVERRIDES
    return normalize_language(overrides.get(language, language))


def prepare_draft(draft_text: str, response_language: str | None = None, ai_disclaimer: str | None = None) -> str:
    """Always prepend a disclaimer, using a model translation for other languages."""
    language = response_language_for(response_language)
    translations = {**DISCLAIMERS, **settings.AI_DISCLAIMER_TRANSLATIONS}
    disclaimer = translations.get(language) or (ai_disclaimer or '').strip()
    if not disclaimer:
        raise ValueError("Fornisci ai_disclaimer tradotto nella lingua della risposta e riprova a salvare la bozza.")
    body = draft_text.strip()
    # Idempotent if the agent already included the configured disclaimer.
    while body.startswith(disclaimer):
        body = body[len(disclaimer):].lstrip()
    if not body:
        raise ValueError("La bozza deve contenere una risposta oltre al disclaimer.")
    return f"{disclaimer}\n\n{body}"

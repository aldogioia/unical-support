# app/ai/prompts.py
from pathlib import Path
import json
from app.core.config import settings

BASE_PROMPTS_DIR = Path(__file__).parent / "prompts_data"

def load_prompt_text(filename: str) -> str:
    file_path = BASE_PROMPTS_DIR / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Prompt {filename} non trovato in {BASE_PROMPTS_DIR}")
    return file_path.read_text(encoding="utf-8")

def get_classifier_system_prompt() -> str:
    return load_prompt_text("classifier.txt")

def get_responder_system_prompt() -> str:
    policy = json.dumps({
        "fallback_language": settings.AI_RESPONSE_FALLBACK_LANGUAGE,
        "body_language_is_authoritative": True,
        "disclaimer_translations": settings.AI_DISCLAIMER_TRANSLATIONS,
    }, ensure_ascii=False)
    return load_prompt_text("responder.txt") + "\n\nPOLITICA LINGUISTICA CONFIGURATA:\n" + policy

def get_md_formatter_system_prompt(source_name: str, reference_url: str | None) -> str:
    metadata = json.dumps({
        "source_name": source_name,
        "reference_url": reference_url,
    }, ensure_ascii=False)
    return load_prompt_text("md_formatter.txt") + "\n\nMETADATI DEL DOCUMENTO:\n" + metadata

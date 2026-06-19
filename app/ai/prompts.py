# app/ai/prompts.py
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate

BASE_PROMPTS_DIR = Path(__file__).parent / "prompts_data"

def load_prompt_text(filename: str) -> str:
    file_path = BASE_PROMPTS_DIR / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Il file di prompt {filename} non esiste in {BASE_PROMPTS_DIR}")
    return file_path.read_text(encoding="utf-8")

def get_classifier_prompt():
    system_text = load_prompt_text("classifier.txt")
    return ChatPromptTemplate.from_messages([
        ("system", system_text),
        ("user", "Mittente: {sender}\nOggetto: {subject}\nCorpo: {body}")
    ])

def get_responder_prompt():
    system_text = load_prompt_text("responder.txt")
    return ChatPromptTemplate.from_messages([
        ("system", system_text),
        ("user", "Email originale dello studente:\nOggetto: {subject}\nCorpo: {body}")
    ])
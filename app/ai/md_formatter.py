import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.ai.llm_factory import get_formatter_llm
from app.ai.prompts import get_md_formatter_system_prompt

WINDOW_CHUNK_SIZE = 6000
WINDOW_CHUNK_OVERLAP = 200

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*\s*%?")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\b\d{2,4}[\s./-]?\d{5,8}\b")
_LAW_REF_RE = re.compile(
    r"\b(?:articolo|art\.?|legge|D\.?P\.?R\.?|D\.?Lgs\.?|decreto legislativo)"
    r"\s+n?\.?\s*\d+(?:[.,]\d+)*(?:\s*(?:del|/)\s*\d{2,4})?",
    re.IGNORECASE,
)

# Pattern usati per riconoscere come e' raggruppato un numero (migliaia vs decimali)
# prima di ricondurlo a una forma canonica unica.
_MIXED_DOT_THOUSANDS_COMMA_DECIMAL_RE = re.compile(r"^\d{1,3}(?:\.\d{3})+,\d+$")
_MIXED_COMMA_THOUSANDS_DOT_DECIMAL_RE = re.compile(r"^\d{1,3}(?:,\d{3})+\.\d+$")
_DOT_THOUSANDS_RE = re.compile(r"^\d{1,3}(?:\.\d{3})+$")
_COMMA_THOUSANDS_RE = re.compile(r"^\d{1,3}(?:,\d{3})+$")
_DOT_DECIMAL_RE = re.compile(r"^\d+\.\d{1,2}$")
_COMMA_DECIMAL_RE = re.compile(r"^\d+,\d{1,2}$")


@dataclass
class NormalizationResult:
    markdown: str
    needs_review: bool
    review_notes: str | None


def _canonical_number(raw: str) -> str:
    """
    Riduce rappresentazioni numeriche equivalenti alla stessa forma canonica:
    "2.000", "2000" e "2,000.00" diventano tutte "2000"; "18,75" e "18.75"
    diventano entrambe "18.75". In questo modo il controllo di fedelta' non
    scatta per una semplice differenza di formattazione (separatore delle
    migliaia presente o assente, virgola/punto come decimale, zero iniziale
    in "07" vs "7"), ma solo quando il VALORE numerico e' davvero diverso.
    """
    token = raw.strip()
    percent = token.endswith("%")
    if percent:
        token = token[:-1].strip()
    if not token:
        return raw.strip()

    if _MIXED_DOT_THOUSANDS_COMMA_DECIMAL_RE.match(token):
        normalized = token.replace(".", "").replace(",", ".")
    elif _MIXED_COMMA_THOUSANDS_DOT_DECIMAL_RE.match(token):
        normalized = token.replace(",", "")
    elif _DOT_THOUSANDS_RE.match(token):
        normalized = token.replace(".", "")
    elif _COMMA_THOUSANDS_RE.match(token):
        normalized = token.replace(",", "")
    elif _COMMA_DECIMAL_RE.match(token):
        normalized = token.replace(",", ".")
    elif _DOT_DECIMAL_RE.match(token):
        normalized = token
    elif "," in token and "." not in token:
        normalized = token.replace(",", ".")
    else:
        normalized = token

    try:
        value = Decimal(normalized)
    except InvalidOperation:
        return raw.strip()

    if value == value.to_integral_value():
        canonical = str(int(value))
    else:
        canonical = format(value, "f").rstrip("0").rstrip(".")
    return canonical + ("%" if percent else "")


def _extract_factual_tokens(text: str) -> set[str]:
    """Elementi verificabili e non parafrasabili: numeri, contatti, riferimenti normativi."""
    tokens: set[str] = set()
    tokens.update(m.strip() for m in _EMAIL_RE.findall(text))
    tokens.update(m.strip() for m in _PHONE_RE.findall(text))
    tokens.update(" ".join(m.split()).lower() for m in _LAW_REF_RE.findall(text))
    tokens.update(_canonical_number(m) for m in _NUMBER_RE.findall(text))
    return {t for t in tokens if t}


def _check_window_fidelity(source: str, generated: str) -> tuple[set[str], set[str]]:
    source_tokens = _extract_factual_tokens(source)
    generated_tokens = _extract_factual_tokens(generated)
    missing = source_tokens - generated_tokens
    extra = generated_tokens - source_tokens
    return missing, extra


def normalize_to_structured_markdown(
    raw_text: str, source_name: str, reference_url: str | None = None
) -> NormalizationResult:
    """
    Riscrive raw_text nel formato "KB atomica" (paragrafi autosufficienti con
    titolo in grassetto e fonte citata) usando l'LLM configurato come responder.
    Confronta numeri/date/contatti/riferimenti normativi tra il testo originale
    e l'output generato, finestra per finestra: se non coincidono esattamente,
    il documento va marcato come needs_review invece di essere indicizzato.
    """
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return NormalizationResult(markdown="", needs_review=False, review_notes=None)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=WINDOW_CHUNK_SIZE, chunk_overlap=WINDOW_CHUNK_OVERLAP
    )
    windows = splitter.split_text(raw_text)

    llm = get_formatter_llm()
    sys_msg = SystemMessage(
        content=get_md_formatter_system_prompt(source_name=source_name, reference_url=reference_url)
    )

    formatted_parts: list[str] = []
    problem_reports: list[str] = []

    for idx, window in enumerate(windows, start=1):
        user_msg = HumanMessage(
            content=f"TESTO ORIGINALE (parte {idx}/{len(windows)}):\n{window}"
        )
        response = llm.invoke([sys_msg, user_msg])
        generated = (response.content or "").strip()
        if not generated:
            continue

        missing, extra = _check_window_fidelity(window, generated)
        if missing or extra:
            details = []
            if missing:
                details.append(f"dati persi: {', '.join(sorted(missing))}")
            if extra:
                details.append(f"dati non presenti nell'originale: {', '.join(sorted(extra))}")
            problem_reports.append(f"Parte {idx}/{len(windows)}: " + "; ".join(details))

        formatted_parts.append(generated)

    markdown = "\n\n".join(formatted_parts)
    needs_review = bool(problem_reports)
    review_notes = "\n".join(problem_reports) if problem_reports else None

    return NormalizationResult(markdown=markdown, needs_review=needs_review, review_notes=review_notes)

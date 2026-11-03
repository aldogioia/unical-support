"""
Elenco dei modelli offerti da un server LLM locale (Ollama, LM Studio, vLLM...),
interrogato dal backend con lo stesso URL che userà il worker: se il server non
è raggiungibile da qui, l'errore si vede subito nella pagina delle impostazioni.

Usa solo la libreria standard (urllib): nessuna dipendenza aggiuntiva.
"""
import json
import logging
import urllib.error
import urllib.request
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 5
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class LocalModelsError(Exception):
    """Il server locale non è raggiungibile o non ha restituito una lista di modelli."""


def _normalize_base_url(base_url: str | None) -> str:
    url = (base_url or "").strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise LocalModelsError("URL non valido: deve iniziare con http:// o https://, es. http://host.docker.internal:11434/v1")
    return url


def _get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    # Nessun proxy: il server LLM è sulla rete locale/Docker, non su Internet.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read(MAX_RESPONSE_BYTES).decode("utf-8"))


def _describe(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"risposta HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return str(exc.reason)
    if isinstance(exc, (TimeoutError, OSError)):
        return str(exc) or exc.__class__.__name__
    if isinstance(exc, ValueError):
        return "risposta non in formato JSON"
    return exc.__class__.__name__


def list_local_models(base_url: str | None) -> list[str]:
    """
    Prova prima l'endpoint standard OpenAI-compatibile `<base_url>/models`
    (Ollama, LM Studio, vLLM), poi quello nativo di Ollama `/api/tags`
    (equivalente a `ollama list`). Restituisce gli identificativi ordinati.
    """
    url = _normalize_base_url(base_url)
    root = url[: -len("/v1")] if url.endswith("/v1") else url
    attempts = [
        (f"{url}/models", lambda data: [m.get("id") for m in data.get("data", [])]),
        (f"{root}/api/tags", lambda data: [m.get("name") or m.get("model") for m in data.get("models", [])]),
    ]

    errors: list[str] = []
    for endpoint, extract in attempts:
        try:
            names = extract(_get_json(endpoint))
        except Exception as exc:
            errors.append(f"{endpoint}: {_describe(exc)}")
            continue
        models = sorted({n.strip() for n in names if isinstance(n, str) and n.strip()})
        if models:
            return models
        errors.append(f"{endpoint}: nessun modello nella risposta")

    logger.warning("Lista modelli locali non disponibile per %s: %s", url, " | ".join(errors))
    raise LocalModelsError(f"Server non raggiungibile o senza modelli ({'; '.join(errors)})")

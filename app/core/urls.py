from pydantic import HttpUrl, TypeAdapter, ValidationError

_http_url = TypeAdapter(HttpUrl)


def normalize_reference_url(value: str | None) -> str | None:
    """Validate the document's only source link without fetching its content."""
    if value is None or not value.strip():
        return None
    value = value.strip()
    if len(value) > 2048:
        raise ValueError("Il link pubblico non può superare 2048 caratteri.")
    try:
        parsed = _http_url.validate_python(value)
    except ValidationError as exc:
        raise ValueError("Inserisci un link pubblico valido che inizi con http:// o https://.") from exc
    if parsed.username or parsed.password:
        raise ValueError("Il link pubblico non deve contenere credenziali.")
    return str(parsed)

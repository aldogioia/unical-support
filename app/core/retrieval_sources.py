"""Bounded, immutable snapshots of passages actually returned by retrieval."""
import json
from uuid import UUID
from app.core.urls import normalize_reference_url


def source_snapshots(context: str) -> list[dict]:
    result = []
    for passage in (context or '').split('\n\n---\n\n'):
        try:
            data = json.loads(passage)
            if not isinstance(data, dict) or not isinstance(data.get('content'), str) or not data['content'].strip():
                continue
            try:
                identifier = str(UUID(str(data.get('document_id'))))
            except (ValueError, TypeError):
                identifier = None
            try:
                url = normalize_reference_url(data.get('reference_url'))
            except (ValueError, TypeError, AttributeError):
                url = None
            page = data.get('page')
            result.append(dict(document_id=identifier,
                source_name=str(data.get('source_name') or 'Documento')[:255], reference_url=url,
                page=str(page)[:40] if isinstance(page, (str, int)) and not isinstance(page, bool) else None,
                excerpt=data['content'].strip()[:2000]))
        except (ValueError, TypeError, AttributeError):
            continue
    return merge_sources([], result)


def merge_sources(existing: list[dict], new: list[dict]) -> list[dict]:
    result, seen = [], set()
    for source in [*existing, *new]:
        key = json.dumps(source, sort_keys=True)
        if key not in seen:
            seen.add(key)
            result.append(source)
    return result[:60]

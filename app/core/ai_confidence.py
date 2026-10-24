"""Retrieval diagnostics, never a calibrated probability of answer correctness."""
import json
import math


def retrieval_confidence(messages) -> float | None:
    scores = []
    for message in messages:
        if getattr(message, 'type', None) != 'tool' or getattr(message, 'name', None) != 'search_knowledge_base':
            continue
        content = getattr(message, 'content', '')
        if not isinstance(content, str):
            continue
        for passage in content.split('\n\n---\n\n'):
            try:
                score = json.loads(passage).get('relevance_score')
            except (ValueError, AttributeError, TypeError):
                continue
            if isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score) and 0 <= score <= 1:
                scores.append(score)
    return round(sum(scores) / len(scores), 4) if scores else None

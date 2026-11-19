import json
from uuid import uuid4
from app.core.retrieval_sources import source_snapshots, merge_sources


def test_source_snapshot_preserves_real_excerpt_and_sanitizes_unsupported_links():
    identifier = str(uuid4())
    result = source_snapshots(json.dumps({'document_id':identifier, 'source_name':'Guida', 'reference_url':'javascript:alert(1)', 'page':2, 'content':'Testo effettivamente recuperato'}))
    assert result == [{'document_id':identifier, 'source_name':'Guida', 'reference_url':None, 'page':'2', 'excerpt':'Testo effettivamente recuperato'}]


def test_sources_deduplicate_repeated_searches_without_losing_distinct_passages():
    context = json.dumps({'source_name':'Guida', 'reference_url':'https://example.org/doc', 'content':'Passaggio A'})
    second = json.dumps({'source_name':'Guida', 'reference_url':'https://example.org/doc', 'content':'Passaggio B'})
    assert len(source_snapshots(context + '\n\n---\n\n' + context)) == 1
    assert len(merge_sources(source_snapshots(context), source_snapshots(second))) == 2
    assert source_snapshots('nessuna fonte disponibile') == []
    assert source_snapshots(json.dumps({'source_name':'Inventata ma senza contenuto'})) == []

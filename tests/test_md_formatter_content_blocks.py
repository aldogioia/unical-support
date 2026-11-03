"""Il formatter accetta anche il contenuto a blocchi restituito dai modelli Gemini recenti."""
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from app.ai import md_formatter

TEXT = '**Seconda rata.** La seconda rata scade il 31 marzo 2027. (Fonte: Regolamento Tasse.)'


def run(content):
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content=content)
    with patch.object(md_formatter, 'get_formatter_llm', return_value=llm):
        return md_formatter.normalize_to_structured_markdown(TEXT, source_name='Regolamento Tasse.pdf')


def test_plain_string_content_still_works():
    result = run(TEXT)
    assert TEXT in result.markdown
    assert not result.needs_review


def test_list_of_content_blocks_from_gemini():
    result = run([{'type': 'thinking', 'thinking': 'ragiono...'}, {'type': 'text', 'text': TEXT}])
    assert TEXT in result.markdown
    assert 'ragiono' not in result.markdown
    assert not result.needs_review


def test_mixed_string_blocks_are_joined():
    half = len(TEXT) // 2
    result = run([TEXT[:half], {'type': 'text', 'text': TEXT[half:]}])
    assert TEXT in result.markdown

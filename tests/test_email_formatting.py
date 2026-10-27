import unittest
from unittest.mock import patch

from app.core.config import settings
from app.core.email_formatting import (
    DISCLAIMERS, LEGACY_DISCLAIMERS, prepare_draft, normalize_email_text,
    get_ai_disclaimer, response_language_for,
)
from app.ai.prompts import get_responder_system_prompt


class EmailFormattingTests(unittest.TestCase):
    def test_single_hard_wraps_join_and_paragraphs_remain(self):
        text = 'Ciao,\r\n\r\nPuoi caricare\r\nil documento entro\r\nvenerdì.\r\n\r\nUn saluto,\r\nSegreteria Unical'
        self.assertEqual(normalize_email_text(text), 'Ciao,\n\nPuoi caricare il documento entro venerdì.\n\nUn saluto, Segreteria Unical')

    def test_lists_preserve_items_and_join_continuations(self):
        text = 'Documenti:\n- Modulo\nfirmato\n* Ricevuta\ndel pagamento\n\n1. Apri\nil portale\n2. Carica il file\n\nGrazie.'
        expected = 'Documenti:\n\n- Modulo firmato\n* Ricevuta del pagamento\n\n1. Apri il portale\n2. Carica il file\n\nGrazie.'
        self.assertEqual(normalize_email_text(text), expected)
        self.assertEqual(normalize_email_text(expected), expected)

    def test_draft_contains_only_answer_and_strips_legacy_notice(self):
        for code, greeting in [('it', 'Ciao,'), ('en', 'Hello,'), ('es', 'Hola,')]:
            self.assertEqual(prepare_draft(LEGACY_DISCLAIMERS[code] + '\n\n' + greeting, code), greeting)
            self.assertEqual(prepare_draft(greeting + '\n\n' + DISCLAIMERS[code], code), greeting)

    def test_other_languages_require_translated_note_but_do_not_prepend_it(self):
        with self.assertRaises(ValueError):
            prepare_draft('こんにちは', 'ja')
        self.assertEqual(prepare_draft('こんにちは', 'ja', '人工知能の支援により作成し、担当者が送信前に確認しました。'), 'こんにちは')

    def test_fallback_and_policy_are_configurable(self):
        with patch.object(settings, 'AI_RESPONSE_FALLBACK_LANGUAGE', 'en'), patch.object(settings, 'AI_RESPONSE_LANGUAGE_OVERRIDES', {'es': 'en'}):
            self.assertEqual(response_language_for('es'), 'es')
            self.assertEqual(response_language_for(None), 'en')
            self.assertEqual(get_ai_disclaimer(), DISCLAIMERS['en'])
            self.assertIn('"fallback_language": "en"', get_responder_system_prompt())
            self.assertIn('"body_language_is_authoritative": true', get_responder_system_prompt())

    def test_configured_note_and_empty_body(self):
        with patch.object(settings, 'AI_DISCLAIMER_TRANSLATIONS', {'it': 'Avviso personalizzato.'}):
            self.assertEqual(get_ai_disclaimer('it'), 'Avviso personalizzato.')
            self.assertEqual(prepare_draft('Avviso personalizzato.\n\nCiao,', 'it'), 'Ciao,')
        for text in ('   ', DISCLAIMERS['it']):
            with self.assertRaises(ValueError):
                prepare_draft(text, 'it')

    def test_prompt_and_agent_have_no_canned_response_tools(self):
        from app.ai import tools
        from app.main import app
        from app.db.database import Base
        self.assertNotIn('get_category_template', get_responder_system_prompt())
        self.assertFalse(hasattr(tools, 'get_category_template'))
        self.assertFalse(any('/api/templates' in path for path in app.openapi()['paths']))
        self.assertFalse(any(name in Base.metadata.tables for name in ('templates', 'template_category')))
        self.assertFalse(any('Template' in name for name in app.openapi()['components']['schemas']))


if __name__ == '__main__':
    unittest.main()

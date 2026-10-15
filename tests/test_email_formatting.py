import unittest
from unittest.mock import patch

from app.core.config import settings
from app.core.email_formatting import DISCLAIMERS, prepare_draft
from app.ai.prompts import get_responder_system_prompt


class EmailFormattingTests(unittest.TestCase):
    def test_disclaimer_precedes_salutation_in_supported_languages(self):
        for code, greeting in [('it', 'Ciao,'), ('en', 'Hello,'), ('es', 'Hola,'), ('fr', 'Bonjour,'), ('de', 'Hallo,'), ('pt', 'Olá,')]:
            with self.subTest(language=code):
                result = prepare_draft(greeting + '\nRisposta', code)
                self.assertTrue(result.startswith(DISCLAIMERS[code] + '\n\n' + greeting))

    def test_disclaimer_is_not_duplicated(self):
        result = prepare_draft(DISCLAIMERS['en'] + '\n\nHello,', 'en-US')
        self.assertEqual(result.count(DISCLAIMERS['en']), 1)

    def test_other_languages_require_translated_disclaimer(self):
        with self.assertRaises(ValueError):
            prepare_draft('こんにちは', 'ja')
        result = prepare_draft('こんにちは', 'ja', 'この返信は人工知能によって生成されました。')
        self.assertTrue(result.startswith('この返信は人工知能によって生成されました。\n\n'))

    def test_fallback_and_policy_are_configurable(self):
        with patch.object(settings, 'AI_RESPONSE_FALLBACK_LANGUAGE', 'en'), patch.object(settings, 'AI_RESPONSE_LANGUAGE_OVERRIDES', {'es': 'en'}):
            self.assertTrue(prepare_draft('Hello,').startswith(DISCLAIMERS['en']))
            self.assertTrue(prepare_draft('Hello,', 'es').startswith(DISCLAIMERS['en']))
            self.assertIn('"fallback_language": "en"', get_responder_system_prompt())
            self.assertIn('"es": "en"', get_responder_system_prompt())

    def test_configured_translation_and_empty_body(self):
        with patch.object(settings, 'AI_DISCLAIMER_TRANSLATIONS', {'it': 'Avviso personalizzato.'}):
            self.assertEqual(prepare_draft('Ciao,', 'it'), 'Avviso personalizzato.\n\nCiao,')
        with self.assertRaises(ValueError):
            prepare_draft('   ', 'it')


if __name__ == '__main__':
    unittest.main()

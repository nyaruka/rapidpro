from unittest.mock import call

from temba.ai.models import LLM
from temba.ai.types.anthropic.type import AnthropicType
from temba.ai.types.openai.type import OpenAIType
from temba.tests import TembaTest, mock_mailroom


class LLMTest(TembaTest):
    def test_model(self):
        openai = LLM.create(self.org, self.admin, OpenAIType.slug, "GPT-4", {})
        LLM.create(self.org, self.admin, AnthropicType.slug, "Claude", {})

        self.assertIsInstance(openai.type, OpenAIType)
        self.assertEqual("GPT-4 (openai)", str(openai))

        openai.release(self.admin)

        self.assertFalse(openai.is_active)
        self.assertEqual(1, LLM.objects.filter(is_active=True).count())
        self.assertEqual(1, LLM.objects.filter(is_active=False).count())
        self.assertEqual(2, LLM.objects.count())

    @mock_mailroom
    def test_translate(self, mr_mocks):
        openai = LLM.create(self.org, self.admin, OpenAIType.slug, "GPT-4", {})

        mr_mocks.llm_translate("Hola")
        self.assertEqual(openai.translate("eng", "spa", "Hello"), "Hola")

        self.assertEqual(call(openai, "eng", "spa", "Hello"), mr_mocks.calls["llm_translate"][-1])

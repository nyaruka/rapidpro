from temba.ai.models import LLM
from temba.ai.types.openai.type import OpenAIType
from temba.tests import TembaTest


class LLMTest(TembaTest):
    def setUp(self):
        super().setUp()

        # create some models
        self.basic = LLM.create(self.org, self.admin, OpenAIType.slug, "Basic", "api_key", "gpt-turbo-3.5")
        self.advanced = LLM.create(self.org, self.admin, OpenAIType.slug, "Advanced", "api_key", "gpt-4o")

    def test_basics(self):
        self.assertEqual("api_key", self.basic.get_api_key())
        self.assertEqual("gpt-turbo-3.5", self.basic.get_model())
        self.assertIsInstance(self.basic.get_type(), OpenAIType)
        self.assertEqual("Basic (openai)", str(self.basic))

    def test_release(self):
        self.basic.release(self.admin)

        self.assertFalse(self.basic.is_active)
        self.assertEqual(1, LLM.objects.filter(is_active=True).count())
        self.assertEqual(1, LLM.objects.filter(is_active=False).count())
        self.assertEqual(2, LLM.objects.count())

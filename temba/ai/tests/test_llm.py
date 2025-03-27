from temba.ai.models import LLM
from temba.ai.types.openai.type import OpenAIType
from temba.tests import TembaTest


class LLMTest(TembaTest):
    def setUp(self):
        super().setUp()

        # create some models
        self.basic = LLM.create(self.org, self.admin, OpenAIType.slug, "Basic", {})
        self.advanced = LLM.create(self.org, self.admin, OpenAIType.slug, "Advanced", {})

    def test_model(self):
        self.assertIsInstance(self.basic.type, OpenAIType)
        self.assertEqual("Basic (openai)", str(self.basic))

        self.basic.release(self.admin)
        self.assertFalse(self.basic.is_active)
        self.assertEqual(1, LLM.objects.filter(is_active=True).count())
        self.assertEqual(1, LLM.objects.filter(is_active=False).count())
        self.assertEqual(2, LLM.objects.count())

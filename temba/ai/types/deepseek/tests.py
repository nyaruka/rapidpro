from unittest.mock import Mock, patch

import openai

from django.urls import reverse

from temba.ai.models import LLM
from temba.tests import TembaTest
from temba.tests.crudl import CRUDLTestMixin


class DeepSeekTypeTest(TembaTest, CRUDLTestMixin):
    @patch("openai.OpenAI")
    def test_connect(self, mock_client):
        connect_url = reverse("ai.types.deepseek.connect")

        self.assertRequestDisallowed(connect_url, [self.editor, self.agent])

        response = self.requestView(connect_url, self.admin, status=200)
        self.assertContains(response, "You can find your API key at https://platform.deepseek.com/api_keys")

        # test with bad api key
        mock_client.return_value.models.list.side_effect = openai.AuthenticationError(
            "Invalid API Key", response=Mock(request=None), body=None
        )
        response = self.process_wizard("connect_view", connect_url, {"credentials": {"api_key": "bad_key"}})
        self.assertContains(response, "Invalid API Key")

        # reset our mock
        mock_client.return_value.models.list.side_effect = None

        # get our model list from an api key
        mock_client.return_value.models.list.return_value = [Mock(id="deepseek-chat"), Mock(id="deepseek-reasoning")]
        response = self.process_wizard("connect_view", connect_url, {"credentials": {"api_key": "good_key"}})
        self.assertEqual(response.context["form"].fields["model"].choices, [("deepseek-chat", "deepseek-chat")])

        # select a model and give it a name
        response = self.process_wizard(
            "connect_view",
            connect_url,
            {"credentials": {"api_key": "good_key"}, "model": {"model": "deepseek-chat"}, "name": {"name": "DeepSeek"}},
        )
        self.assertRedirects(response, reverse("ai.llm_list"))

        # check that we created our model
        llm = LLM.objects.get(org=self.org, llm_type="deepseek")
        self.assertEqual("DeepSeek", llm.name)
        self.assertEqual("deepseek-chat", llm.model)
        self.assertEqual("good_key", llm.config["api_key"])

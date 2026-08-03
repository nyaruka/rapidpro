from unittest.mock import Mock, patch

import openai

from django.urls import reverse

from temba.ai.models import LLM
from temba.ai.types.openai_azure.type import OpenAIAzureType
from temba.tests import TembaTest
from temba.tests.crudl import CRUDLTestMixin


class OpenAIAzureTypeTest(TembaTest, CRUDLTestMixin):
    @patch("openai.AzureOpenAI")
    def test_connect(self, mock_client):
        connect_url = reverse("ai.llm_connect")

        self.assertRequestDisallowed(connect_url, [self.editor, self.agent])

        response = self.requestView(connect_url, self.admin, status=200)
        response = self.process_wizard("connect", connect_url, {"provider": {"provider": "openai_azure"}})
        self.assertContains(response, "API keys are provided")

        # test with bad api key
        mock_client.return_value.chat.completions.create.side_effect = openai.AuthenticationError(
            "Invalid API Key", response=Mock(request=None), body=None
        )
        response = self.process_wizard("connect", connect_url, {"credentials": {"api_key": "bad_key"}})
        self.assertContains(response, "Invalid API Key")

        # reset our mock
        mock_client.return_value.chat.completions.create.side_effect = None

        # get our model list
        response = self.process_wizard("connect", connect_url, {"credentials": {"api_key": "good_key"}})
        expected_models = [(m, m) for m in OpenAIAzureType().settings["models"]]
        self.assertEqual(response.context["form"].fields["model"].choices, expected_models)

        # select a model and give it a name
        response = self.process_wizard(
            "connect",
            connect_url,
            {
                "credentials": {"api_key": "good_key"},
                "model": {"model": "gpt-35-turbo", "name": "Support Assistant"},
            },
        )
        self.assertRedirects(response, reverse("ai.llm_list"))

        # check that we created our model
        llm = LLM.objects.get(org=self.org, llm_type="openai_azure")
        self.assertEqual("Support Assistant", llm.name)
        self.assertEqual("gpt-35-turbo", llm.model)
        self.assertEqual("https://orgunit-ai-endpoints.azure-api.net/openai-gen-ai-poc", llm.config["endpoint"])
        self.assertEqual("good_key", llm.config["api_key"])

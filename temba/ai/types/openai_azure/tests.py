from unittest.mock import Mock, patch

import openai

from django.urls import reverse

from temba.ai.models import LLM
from temba.tests import TembaTest
from temba.tests.crudl import CRUDLTestMixin


class OpenAIAzureTypeTest(TembaTest, CRUDLTestMixin):
    @patch("openai.AzureOpenAI")
    def test_connect(self, mock_client):
        connect_url = reverse("ai.types.openai_azure.connect")

        self.assertRequestDisallowed(connect_url, [self.editor, self.agent])
        self.assertCreateFetch(connect_url, [self.admin], form_fields=("endpoint", "api_key", "deployment"))

        # test with bad endpoint
        mock_client.return_value.chat.completions.create.side_effect = openai.APIConnectionError(request=Mock())
        response = self.process_wizard(
            "connect_view",
            connect_url,
            {"connect": {"endpoint": "http://nope", "api_key": "sesame", "deployment": "gpt-4"}},
        )
        self.assertContains(response, "Please check your endpoint URL.")

        # test with bad api key
        mock_client.return_value.chat.completions.create.side_effect = openai.AuthenticationError(
            "Invalid API Key", response=Mock(request=None), body=None
        )
        response = self.process_wizard(
            "connect_view",
            connect_url,
            {"connect": {"endpoint": "http://azure", "api_key": "bad-key", "deployment": "gpt-4"}},
        )
        self.assertContains(response, "Please check your API key.")

        # test with bad deployment name
        mock_client.return_value.chat.completions.create.side_effect = openai.NotFoundError(
            "Invalid Deployment", response=Mock(request=None), body=None
        )
        response = self.process_wizard(
            "connect_view",
            connect_url,
            {"connect": {"endpoint": "http://azure", "api_key": "sesame", "deployment": "foo"}},
        )
        self.assertContains(response, "Please check your deployment name.")

        # reset our mock
        mock_client.return_value.chat.completions.create.side_effect = None

        # select a model and give it a name
        response = self.process_wizard(
            "connect_view",
            connect_url,
            {
                "connect": {"endpoint": "http://azure", "api_key": "sesame", "deployment": "gpt-4"},
                "name": {"name": "Cool Model"},
            },
        )
        self.assertRedirects(response, reverse("ai.llm_list"))

        # check that we created our model
        llm = LLM.objects.get(org=self.org, llm_type="openai_azure")
        self.assertEqual("Cool Model", llm.name)
        self.assertEqual("gpt-4", llm.model)
        self.assertEqual("http://azure", llm.config["endpoint"])
        self.assertEqual("sesame", llm.config["api_key"])

from unittest.mock import Mock, patch

import anthropic

from django.urls import reverse

from temba.ai.models import LLM
from temba.tests import TembaTest
from temba.tests.crudl import CRUDLTestMixin


class AnthropicTypeTest(TembaTest, CRUDLTestMixin):
    @patch("anthropic.Anthropic")
    def test_connect(self, mock_client):
        connect_url = reverse("ai.types.anthropic.connect")

        self.assertRequestDisallowed(connect_url, [self.editor, self.agent])

        response = self.requestView(connect_url, self.admin, status=200)
        self.assertContains(response, "You can find your API key at https://console.anthropic.com/settings/keys")

        # test with bad api key
        mock_client.return_value.models.list.side_effect = anthropic.AuthenticationError(
            "Invalid API Key", response=Mock(request=None), body=None
        )
        response = self.process_wizard("connect_view", connect_url, {"credentials": {"api_key": "bad_key"}})
        self.assertContains(response, "Invalid API Key")

        # reset our mock
        mock_client.return_value.models.list.side_effect = None

        # get our model list from an api key
        mock_client.return_value.models.list.return_value = [
            Mock(id="claude-opus-4-8", display_name="Claude Opus 4.8"),
            Mock(id="claude-sonnet-5", display_name="Claude Sonnet 5"),
            Mock(id="claude-3-5-sonnet-20240620", display_name="Claude 3.5 Sonnet (Old)"),
        ]
        response = self.process_wizard("connect_view", connect_url, {"credentials": {"api_key": "good_key"}})
        self.assertEqual(
            response.context["form"].fields["model"].choices,
            [
                ("claude-opus-4-8", "Claude Opus 4.8"),
                ("claude-sonnet-5", "Claude Sonnet 5"),
            ],
        )

        # select a model and give it a name
        response = self.process_wizard(
            "connect_view",
            connect_url,
            {
                "credentials": {"api_key": "good_key"},
                "model": {"model": "claude-sonnet-5"},
                "name": {"name": "Claude"},
            },
        )
        self.assertRedirects(response, reverse("ai.llm_list"))

        # check that we created our model
        llm = LLM.objects.get(org=self.org, llm_type="anthropic")
        self.assertEqual("Claude", llm.name)
        self.assertEqual("claude-sonnet-5", llm.model)
        self.assertEqual("good_key", llm.config["api_key"])

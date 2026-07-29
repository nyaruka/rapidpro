from unittest.mock import Mock, patch

from google.genai import errors

from django.urls import reverse

from temba.ai.models import LLM
from temba.tests import TembaTest
from temba.tests.crudl import CRUDLTestMixin


class GoogleTypeTest(TembaTest, CRUDLTestMixin):
    @patch("google.genai.Client")
    def test_connect(self, mock_client):
        connect_url = reverse("ai.llm_connect")

        self.assertRequestDisallowed(connect_url, [self.editor, self.agent])

        response = self.requestView(connect_url, self.admin, status=200)
        response = self.process_wizard("connect", connect_url, {"provider": {"provider": "google"}})
        self.assertContains(response, "You can find your API key at https://aistudio.google.com/")

        # test with bad api key
        mock_client.return_value.models.list.side_effect = errors.ClientError(403, {})
        response = self.process_wizard("connect", connect_url, {"credentials": {"api_key": "bad_key"}})
        self.assertContains(response, "Invalid API Key")

        # reset our mock
        mock_client.return_value.models.list.side_effect = None

        # get our model list from an api key
        mock_models = [
            Mock(display_name="Gemini 3.6 Flash"),
            Mock(display_name="Gemini 2.5 Flash"),
            Mock(display_name="Gemini 1.5 Flash"),
        ]

        # because https://docs.python.org/3/library/unittest.mock.html#mock-names-and-the-name-attribute
        mock_models[0].name = "models/gemini-3.6-flash"
        mock_models[1].name = "models/gemini-2.5-flash"
        mock_models[2].name = "models/gemini-1.5-flash"
        mock_client.return_value.models.list.return_value = mock_models

        response = self.process_wizard("connect", connect_url, {"credentials": {"api_key": "good_key"}})
        self.assertEqual(
            response.context["form"].fields["model"].choices,
            [("gemini-3.6-flash", "Gemini 3.6 Flash"), ("gemini-2.5-flash", "Gemini 2.5 Flash")],
        )

        # select a model and give it a name
        response = self.process_wizard(
            "connect",
            connect_url,
            {
                "credentials": {"api_key": "good_key"},
                "model": {"model": "gemini-2.5-flash", "name": "Translation Assistant"},
            },
        )
        self.assertRedirects(response, reverse("ai.llm_list"))

        # check that we created our model
        llm = LLM.objects.get(org=self.org, llm_type="google")
        self.assertEqual("Translation Assistant", llm.name)
        self.assertEqual("gemini-2.5-flash", llm.model)
        self.assertEqual("good_key", llm.config["api_key"])

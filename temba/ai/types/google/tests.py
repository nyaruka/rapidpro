from unittest.mock import Mock, patch

from google.genai import errors

from django.urls import reverse

from temba.ai.models import LLM
from temba.tests import TembaTest
from temba.tests.crudl import CRUDLTestMixin


class GoogleTypeTest(TembaTest, CRUDLTestMixin):
    @patch("google.genai.Client")
    def test_connect(self, mock_client):
        connect_url = reverse("ai.types.google.connect")

        self.assertRequestDisallowed(connect_url, [self.editor, self.agent])

        response = self.requestView(connect_url, self.admin, status=200)
        self.assertContains(response, "You can find your API key at https://aistudio.google.com/")

        # test with bad api key
        mock_client.return_value.models.list.side_effect = errors.ClientError(403, {})
        response = self.process_wizard("connect_view", connect_url, {"credentials": {"api_key": "bad_key"}})
        self.assertContains(response, "Invalid API Key")

        # reset our mock
        mock_client.return_value.models.list.side_effect = None

        # get our model list from an api key
        mock_models = [
            Mock(display_name="Gemini 2.0 Flash"),
            Mock(display_name="Gemini 1.5 Flash"),
            Mock(display_name="Gemini 1.0 Flash"),
        ]

        # because https://docs.python.org/3/library/unittest.mock.html#mock-names-and-the-name-attribute
        mock_models[0].name = "models/gemini-2.0-flash"
        mock_models[1].name = "models/gemini-1.5-flash"
        mock_models[2].name = "models/gemini-1.0-flash"
        mock_client.return_value.models.list.return_value = mock_models

        response = self.process_wizard("connect_view", connect_url, {"credentials": {"api_key": "good_key"}})
        self.assertEqual(
            response.context["form"].fields["model"].choices,
            [("models/gemini-2.0-flash", "Gemini 2.0 Flash"), ("models/gemini-1.5-flash", "Gemini 1.5 Flash")],
        )

        # select a model and give it a name
        response = self.process_wizard(
            "connect_view",
            connect_url,
            {
                "credentials": {"api_key": "good_key"},
                "model": {"model": "models/gemini-1.5-flash"},
                "name": {"name": "Gemini"},
            },
        )
        self.assertRedirects(response, reverse("ai.llm_list"))

        # check that we created our model
        llm = LLM.objects.get(org=self.org, llm_type="google")
        self.assertEqual("Gemini", llm.name)
        self.assertEqual("gemini-1.5-flash", llm.model)
        self.assertEqual("good_key", llm.config["api_key"])

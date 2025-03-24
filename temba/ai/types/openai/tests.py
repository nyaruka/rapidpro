from unittest.mock import Mock, patch

import openai

from django.urls import reverse

from temba.ai.models import LLM
from temba.ai.types.openai.type import OpenAIType
from temba.tests import TembaTest
from temba.tests.crudl import CRUDLTestMixin


class OpenAITypeTest(TembaTest, CRUDLTestMixin):

    @patch("openai.OpenAI")
    def test_connect(self, mock_openai):

        def get_models(model_list):
            return [Mock(**m) for m in model_list]

        connect_url = reverse("ai.types.openai.connect")

        self.assertRequestDisallowed(connect_url, [self.editor, self.agent])

        response = self.requestView(connect_url, self.admin, status=200)
        self.assertContains(response, "You can find your API key at https://platform.openai.com/account/api-key")

        # test with bad api key,
        mock_openai.return_value.models.list.side_effect = openai.AuthenticationError(
            "Invalid API Key", response=Mock(request=None), body=None
        )
        response = self.process_wizard("connect_view", connect_url, {"connect": {"api_key": "bad_key"}})
        self.assertContains(response, "Invalid API Key")

        # reset our mock
        mock_openai.return_value.models.list.side_effect = None

        # get our model list from an api key
        mock_openai.return_value.models.list.return_value = get_models([{"id": "gpt-4o"}, {"id": "gpt-turbo-3.5"}])
        response = self.process_wizard("connect_view", connect_url, {"connect": {"api_key": "good_key"}})
        self.assertContains(response, "gpt-4o")

        # select a model
        response = self.process_wizard(
            "connect_view",
            connect_url,
            {"connect": {"api_key": "good_key"}, "model": {"model": "gpt-4o"}, "name": {"name": "Basic Model"}},
        )

        # check that we created our model
        llm = LLM.objects.get(name="Basic Model", llm_type=OpenAIType.slug)

        # check our config has what we need
        self.assertEqual("good_key", llm.config["api_key"])
        self.assertEqual("gpt-4o", llm.config["model"])

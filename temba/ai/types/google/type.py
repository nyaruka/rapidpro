from google import genai
from google.genai import errors

from django.utils.translation import gettext_lazy as _

from temba.ai.models import LLMCredentialsError, LLMType


class GoogleType(LLMType):
    """
    Type for Google models (Gemini etc)
    """

    name = "Google"
    slug = "google"
    icon = "ai_google"
    api_key_help = _("You can find your API key at https://aistudio.google.com/")

    def get_model_choices(self, api_key):
        try:
            available_models = list(genai.Client(api_key=api_key).models.list(config={"page_size": 10}))
        except errors.ClientError as e:
            raise LLMCredentialsError(_("Invalid API Key.")) from e

        allowed_models = self.settings.get("models", [])
        return [
            (m.name.removeprefix("models/"), m.display_name)
            for m in available_models
            if not allowed_models or m.name.removeprefix("models/") in allowed_models
        ]

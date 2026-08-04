import openai

from django.utils.translation import gettext_lazy as _

from temba.ai.models import LLMCredentialsError, LLMType


class OpenAIType(LLMType):
    """
    Type for OpenAI models (GPT etc)
    """

    name = "OpenAI"
    slug = "openai"
    icon = "ai_openai"
    api_key_help = _("You can find your API key at https://platform.openai.com/account/api-key")

    def get_model_choices(self, api_key):
        try:
            available_models = openai.OpenAI(api_key=api_key).models.list()
        except openai.AuthenticationError as e:
            raise LLMCredentialsError(_("Invalid API Key.")) from e

        allowed_models = self.settings.get("models", [])
        return [(m.id, m.id) for m in available_models if not allowed_models or m.id in allowed_models]

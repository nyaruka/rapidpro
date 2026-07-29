import anthropic

from django.utils.translation import gettext_lazy as _

from temba.ai.models import LLMCredentialsError, LLMType


class AnthropicType(LLMType):
    """
    Type for Anthropic models (Claude etc)
    """

    name = "Anthropic"
    slug = "anthropic"
    icon = "ai_anthropic"
    api_key_help = _("You can find your API key at https://console.anthropic.com/settings/keys")

    def get_model_choices(self, api_key):
        try:
            available_models = anthropic.Anthropic(api_key=api_key).models.list()
        except anthropic.AuthenticationError as e:
            raise LLMCredentialsError(_("Invalid API Key.")) from e

        allowed_models = self.settings.get("models", [])
        return [(m.id, m.display_name) for m in available_models if not allowed_models or m.id in allowed_models]

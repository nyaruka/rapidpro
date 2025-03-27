from django.utils.translation import gettext_lazy as _

from temba.ai.models import LLMType
from temba.ai.types.openai.views import ConnectView


class AnthropicType(LLMType):
    """
    Type for Anthropic models (Claude etc)
    """

    name = "Anthropic"
    slug = "anthropic"
    icon = "anthropic"
    connect_blurb = _(
        "If you have an existing Anthropic account, you can add it to your workspace and use it for AI tasks."
    )

    form_blurb = _("To connect your Anthropic account, please provide your API key.")
    connect_view = ConnectView

    CONFIG_API_KEY = "api_key"
    CONFIG_MODEL = "model"

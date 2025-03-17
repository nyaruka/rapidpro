from django.utils.translation import gettext_lazy as _

from temba.ai.models import LLMType
from temba.ai.types.openai.views import ConnectView


class OpenAIType(LLMType):
    """
    Type for OpenAI models (GPT)
    """

    name = "OpenAI"
    slug = "openai"
    icon = "icon-openai"
    connect_blurb = _(
        "If you have an existing OpenAI account, you can add it to your workspace and use it for AI tasks."
    )

    form_blurb = _(
        "To connect your OpenAI account, please provide your API key. "
        "You can find your API key in your OpenAI dashboard."
    )

    connect_view = ConnectView

    CONFIG_API_KEY = "api_key"
    CONFIG_MODEL = "model"

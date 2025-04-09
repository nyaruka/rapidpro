from temba.ai.models import LLMType

from .views import ConnectView


class OpenAIType(LLMType):
    """
    Type for OpenAI models (GPT etc)
    """

    name = "OpenAI"
    slug = "openai"
    icon = "openai"

    connect_view = ConnectView

    CONFIG_API_KEY = "api_key"

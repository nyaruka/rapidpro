from temba.ai.models import LLMType

from .views import ConnectView


class OpenAIAzureType(LLMType):
    """
    Type for OpenAI via Microsoft Azure.
    """

    name = "OpenAI (Azure)"
    slug = "openai_azure"
    icon = "openai_azure"

    connect_view = ConnectView

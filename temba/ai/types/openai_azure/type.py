from temba.ai.models import LLMType

from .views import ConnectView


class OpenAIAzureType(LLMType):
    """
    Type for OpenAI models hosted in MS Azure but for now presented in UI as type specific to UNICEF deployments with
    a hardcoded endpoint.
    """

    name = "Azure OpenAI"
    slug = "openai_azure"
    icon = "ai_microsoft"

    connect_view = ConnectView

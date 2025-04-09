from temba.ai.models import LLMType

from .views import ConnectView


class DeepSeekType(LLMType):
    """
    Type for DeepSeek models
    """

    name = "DeepSeek"
    slug = "deepseek"
    icon = "deepseek"

    connect_view = ConnectView

    CONFIG_API_KEY = "api_key"

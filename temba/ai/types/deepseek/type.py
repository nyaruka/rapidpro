from temba.ai.models import LLMType

from .views import ConnectView


class DeepSeekType(LLMType):
    """
    Type for DeepSeek models
    """

    name = "DeepSeek"
    slug = "deepseek"
    icon = "ai_deepseek"

    connect_view = ConnectView

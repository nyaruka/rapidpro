from temba.ai.models import LLMType

from .views import ConnectView


class AnthropicType(LLMType):
    """
    Type for Anthropic models (Claude etc)
    """

    name = "Anthropic"
    slug = "anthropic"
    icon = "ai_anthropic"

    connect_view = ConnectView

from temba.ai.models import LLMType

from .views import ConnectView


class GoogleType(LLMType):
    """
    Type for Google models (Gemini etc)
    """

    name = "Google"
    slug = "google"
    icon = "google"

    connect_view = ConnectView

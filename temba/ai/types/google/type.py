from temba.ai.models import LLMType


class GoogleType(LLMType):
    """
    Type for Google models (Gemini etc)
    """

    name = "Google"
    slug = "google"
    icon = "google"

    def get_urls(self):
        """
        TODO
        """
        return []

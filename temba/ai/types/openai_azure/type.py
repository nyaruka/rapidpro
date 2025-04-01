from temba.ai.models import LLMType


class OpenAIAzureType(LLMType):
    """
    Type for OpenAI via Microsoft Azure.
    """

    name = "UNICEF OpenAI"
    slug = "openai_azure"
    icon = "unicef"

    def get_urls(self):
        """
        TODO
        """
        return []

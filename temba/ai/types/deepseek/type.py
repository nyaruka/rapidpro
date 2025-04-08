from temba.ai.models import LLMType


class DeepSeekType(LLMType):
    """
    Type for DeepSeek models
    """

    name = "DeepSeek"
    slug = "deepseek"
    icon = "deepseek"

    def get_urls(self):
        """
        TODO
        """
        return []

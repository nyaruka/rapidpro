import openai

from django.utils.translation import gettext_lazy as _

from temba.ai.models import LLMType
from temba.ai.types.openai.views import ConnectView


class OpenAIType(LLMType):
    """
    Type for OpenAI models (GPT)
    """

    name = "OpenAI"
    slug = "openai"
    icon = "openai"
    connect_blurb = _(
        "If you have an existing OpenAI account, you can add it to your workspace and use it for AI tasks."
    )

    form_blurb = _("To connect your OpenAI account, please provide your API key. ")
    connect_view = ConnectView

    CONFIG_API_KEY = "api_key"
    CONFIG_MODEL = "model"

    def translate(self, text, lang_from, lang_to, config):
        """
        Translates the given text from one language to another
        """
        api_key = config.get(self.CONFIG_API_KEY)
        model = config.get(self.CONFIG_MODEL)

        client = openai.OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model,
            instructions=f"Translate the given text using languages with the ISO codes from {lang_from} to {lang_to}. The @ indicates a variable expression and should be left alone. Only return the translated text",
            input=text,
        )
        return response.output_text

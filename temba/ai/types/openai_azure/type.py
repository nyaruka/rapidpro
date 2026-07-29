import openai

from django.utils.translation import gettext_lazy as _

from temba.ai.models import LLMCredentialsError, LLMType


class OpenAIAzureType(LLMType):
    """
    Type for OpenAI models hosted in MS Azure but for now presented in UI as type specific to UNICEF deployments with
    a hardcoded endpoint.
    """

    name = "Azure OpenAI"
    slug = "openai_azure"
    icon = "ai_microsoft"
    api_key_help = _("API keys are provided by the UNICEF ICTD team.")
    endpoint = "https://orgunit-ai-endpoints.azure-api.net/openai-gen-ai-poc"

    def get_model_choices(self, api_key):
        endpoint = self.endpoint + "/openai"  # mailroom using go client appends this
        model = next(iter(self.settings["models"]))
        try:
            client = openai.AzureOpenAI(base_url=endpoint, api_key=api_key, api_version="2025-03-01-preview")
            client.chat.completions.create(model=model, messages=[{"role": "user", "content": "How are you?"}])
        except openai.AuthenticationError as e:
            raise LLMCredentialsError(_("Invalid API Key.")) from e

        return [(m, m) for m in self.settings["models"]]

    def get_config(self, api_key):
        return {"endpoint": self.endpoint, "api_key": api_key}

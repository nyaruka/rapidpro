import openai

from django import forms
from django.http import HttpResponseRedirect
from django.utils.translation import gettext_lazy as _

from temba.ai.models import LLM
from temba.ai.views import BaseConnectWizard, NameForm
from temba.utils.fields import InputWidget


class ConnectForm(BaseConnectWizard.Form):
    endpoint = forms.CharField(label=_("Endpoint"), widget=InputWidget())
    api_key = forms.CharField(label=_("API Key"), widget=InputWidget())
    deployment = forms.CharField(
        label=_("Deployment"),
        widget=InputWidget(),
        help_text=_("This is typically the name of the model."),
    )

    def clean(self):
        cleaned_data = super().clean()

        endpoint = cleaned_data.get("endpoint")
        api_key = cleaned_data.get("api_key")
        deployment = cleaned_data.get("deployment")

        if endpoint and api_key and deployment:
            endpoint = endpoint.removesuffix("/") + "/openai"  # mailroom using go client appends this
            try:
                client = openai.AzureOpenAI(base_url=endpoint, api_key=api_key, api_version="2025-03-01-preview")
                client.chat.completions.create(model=deployment, messages=[{"role": "user", "content": "How are you?"}])
            except openai.APIConnectionError:
                raise forms.ValidationError(_("Unable to connect. Please check your endpoint URL."))
            except openai.AuthenticationError:
                raise forms.ValidationError(_("Unable to connect. Please check your API key."))
            except openai.NotFoundError:
                raise forms.ValidationError(_("Unable to connect. Please check your deployment name."))

        return cleaned_data


class ConnectView(BaseConnectWizard):
    form_list = [("connect", ConnectForm), ("name", NameForm)]

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)

        if step == "name":
            kwargs["model_name"] = ""

        return kwargs

    def done(self, form_list, form_dict, **kwargs):
        endpoint = form_dict["connect"].cleaned_data["endpoint"]
        api_key = form_dict["connect"].cleaned_data["api_key"]
        model = form_dict["connect"].cleaned_data["deployment"]
        name = form_dict["name"].cleaned_data["name"]

        self.object = LLM.create(
            self.request.org, self.request.user, self.llm_type, model, name, {"endpoint": endpoint, "api_key": api_key}
        )

        return HttpResponseRedirect(self.get_success_url())

import openai

from django import forms
from django.http import HttpResponseRedirect
from django.utils.translation import gettext_lazy as _

from temba.ai.models import LLM
from temba.ai.views import BaseConnectWizard
from temba.utils.fields import InputWidget, SelectWidget


class ConnectForm(BaseConnectWizard.Form):
    api_key = forms.CharField(
        widget=InputWidget({"placeholder": "API Key", "widget_only": False, "label": "API Key", "value": ""}),
        label="",
        help_text=_("You can find your API key at https://platform.openai.com/account/api-key"),
    )

    def clean_api_key(self):
        api_key = self.data["connect-api_key"]

        try:
            client = openai.OpenAI(api_key=api_key)
            available_models = client.models.list()
        except openai.AuthenticationError:
            raise forms.ValidationError(_("Invalid API Key"))

        allowed_models = self.llm_type.settings.get("models", [])
        model_choices = [(m.id, m.id) for m in available_models if not allowed_models or m.id in allowed_models]

        self.extra_data = {"model_choices": model_choices}  # save our model choices as extra data

        return api_key


class ModelForm(BaseConnectWizard.Form):
    model = forms.ChoiceField(
        label=_("Model"), widget=SelectWidget(), help_text=_("Choose the model you would like to use.")
    )

    def __init__(self, model_choices, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["model"].choices = model_choices


class NameForm(BaseConnectWizard.Form):
    name = forms.CharField(
        label=_("Name"), widget=InputWidget(), help_text=_("Give your model a memorable name."), required=True
    )

    def __init__(self, model_name, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["name"].initial = model_name.replace("gpt", "GPT").replace("-", " ")

    def clean_name(self):
        name = self.cleaned_data["name"]

        # make sure the name isn't already taken
        if self.org.llms.filter(is_active=True, name__iexact=name).exists():
            raise forms.ValidationError(_("Must be unique."))

        return name


class ConnectView(BaseConnectWizard):
    form_list = [("connect", ConnectForm), ("model", ModelForm), ("name", NameForm)]

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)

        if step == "model":
            step_data = self.storage.data["step_data"]
            kwargs["model_choices"] = step_data.get("connect", {}).get("model_choices", [[]])[0]

        if step == "name":
            step_data = self.storage.data["step_data"]
            kwargs["model_name"] = step_data.get("model", {}).get("model-model", [""])[0]

        return kwargs

    def done(self, form_list, form_dict, **kwargs):
        connect_form = form_dict.get("connect")
        model_form = form_dict.get("model")
        name = form_dict.get("name").cleaned_data["name"] or model_form.cleaned_data["model"]

        self.object = LLM.create(
            self.request.org,
            self.request.user,
            self.llm_type,
            name,
            {"api_key": connect_form.cleaned_data["api_key"], "model": model_form.cleaned_data["model"]},
        )

        return HttpResponseRedirect(self.get_success_url())

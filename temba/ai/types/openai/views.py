from django import forms

from django.conf import settings


from django.http import HttpResponseRedirect
from temba.ai.models import LLM

from temba.orgs.views.mixins import OrgPermsMixin
from temba.utils.fields import InputWidget, SelectWidget
from temba.utils.views.wizard import SmartWizardView
from django.utils.translation import gettext_lazy as _

import openai


class ConnectForm(forms.Form):
    api_key = forms.CharField(
        widget=InputWidget(
            {
                "placeholder": "API Key",
                "widget_only": False,
                "label": "API Key",
                "value": "",
            }
        ),
        label="",
        help_text=_("You can find your API key at https://platform.openai.com/account/api-key"),
    )

    def clean_api_key(self):
        api_key = self.data.get("connect-api_key")
        client = openai.OpenAI(api_key=api_key)
        try:
            models = settings.LLM_PROVIDERS.get("temba.ai.types.openai.type.OpenAIType").get("models", [])
            available_models = client.models.list()
            model_choices = [(model.id, model.id) for model in available_models if not models or model.id in models]

            # save our model choices as extra data
            self.extra_data = {"model_choices": model_choices}

        except openai.AuthenticationError:
            raise forms.ValidationError(_("Invalid API Key"))

        return api_key

    def clean(self):
        return self.cleaned_data


class ModelForm(forms.Form):
    model = forms.ChoiceField(
        label="Model", widget=SelectWidget(), help_text=_("Choose the OpenAI model you would like to use")
    )

    def __init__(self, *args, **kwargs):
        model_choices = kwargs.pop("model_choices", [])
        super().__init__(*args, **kwargs)
        self.fields["model"].choices = model_choices


class NameForm(forms.Form):
    name = forms.CharField(
        label="Name", widget=InputWidget(), help_text=_("Give your model a memorable name"), required=False
    )

    def __init__(self, placeholder, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs["placeholder"] = placeholder


class ConnectView(OrgPermsMixin, SmartWizardView):
    form_list = [("connect", ConnectForm), ("model", ModelForm), ("name", NameForm)]

    permission = "ai.llm_connect"
    llm_type = None
    menu_path = "/settings/ai/new-model"
    template_name = "ai/llm_connect_form.html"
    success_url = "@ai.llm_list"

    def __init__(self, llm_type, *args, **kwargs):
        self.llm_type = llm_type
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        if step == "model":
            step_data = self.storage.data["step_data"]
            kwargs["model_choices"] = step_data.get("connect", {}).get("model_choices", [[]])[0]

        if step == "name":
            step_data = self.storage.data["step_data"]
            kwargs["placeholder"] = f"My {step_data.get("model", {}).get("model-model", [""])[0]} model (optional)"

        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_blurb"] = self.llm_type.get_form_blurb()
        return context

    def done(self, form_list, form_dict, **kwargs):
        from .type import OpenAIType

        connect_form = form_dict.get("connect")
        model_form = form_dict.get("model")
        name = form_dict.get("name").cleaned_data["name"] or model_form.cleaned_data["model"]

        self.object = LLM.create(
            self.request.org,
            self.request.user,
            OpenAIType.slug,
            name,
            connect_form.cleaned_data["api_key"],
            model_form.cleaned_data["model"],
        )
        return HttpResponseRedirect(self.get_success_url())

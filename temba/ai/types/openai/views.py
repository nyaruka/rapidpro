from django import forms
from django.urls import reverse

from django.conf import settings


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
        print("cleaning api key...")
        api_key = self.data.get("connect-api_key")
        client = openai.OpenAI(api_key=api_key)

        try:
            models = settings.LLM_PROVIDERS.get("temba.ai.types.openai.type.OpenAIType").get("models", [])
            print("Requesting models...")
            available_models = client.models.list()
            print("done.")
            # breakpoint()
            self.cleaned_data["model_choices"] = [
                (model.id, model.id) for model in available_models if not models or model.id in models
            ]

        except openai.AuthenticationError:
            raise forms.ValidationError(_("Invalid API Key"))

        return api_key

    def clean(self):
        breakpoint()
        self.cleaned_data["model_choices"] = self.model_choices
        return self.cleaned_data


class ChooseForm(forms.Form):

    model_name = forms.ChoiceField(label="Model Name", widget=SelectWidget())

    def __init__(self, *args, **kwargs):
        model_choices = kwargs.pop("model_choices", [])
        super().__init__(*args, **kwargs)
        self.fields["model_name"].choices = model_choices


class ConnectView(OrgPermsMixin, SmartWizardView):
    form_list = [("connect", ConnectForm), ("choose", ChooseForm)]

    permission = "ai.llm_connect"
    llm_type = None
    menu_path = "/settings/ai/new-model"

    template_name = "ai/llm_connect_form.html"

    def __init__(self, llm_type, *args, **kwargs):
        self.llm_type = llm_type
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        if step == "choose":
            print("looking up model choices...")

            # step_data = self.get_cleaned_data_for_step("connect")
            # print(step_data)
            breakpoint()
            step_data = None
            if step_data:
                kwargs["model_choices"] = step_data.get("model_choices", [])
            else:
                kwargs["model_choices"] = []
        return kwargs

    def get_success_url(self):
        return reverse("ai.llm_read", args=[self.object.uuid])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_blurb"] = self.llm_type.get_form_blurb()
        return context

    def done(self, form_list, form_dict, **kwargs):
        # from .type import LLMType
        # self.object = LLM.create(self.request.org, self.request.user, LLMType.slug, form.cleaned_data["name"])
        pass

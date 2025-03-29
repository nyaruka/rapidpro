import json

from smartmin.views import SmartCRUDL, SmartUpdateView

from django import forms
from django.http import JsonResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt

from temba.orgs.views.base import BaseDependencyDeleteModal, BaseListView, BaseUpdateModal
from temba.orgs.views.mixins import OrgObjPermsMixin, OrgPermsMixin, UniqueNameMixin
from temba.tests import mailroom
from temba.utils.views.mixins import ContextMenuMixin, SpaMixin
from temba.utils.views.wizard import SmartWizardView

from .models import LLM


class BaseConnectWizard(OrgPermsMixin, SmartWizardView):
    class Form(forms.Form):
        def __init__(self, org, llm_type, *args, **kwargs):
            super().__init__(*args, **kwargs)

            self.org = org
            self.llm_type = llm_type

    permission = "ai.llm_connect"
    menu_path = "/settings/ai/new-model"
    template_name = "ai/llm_connect_form.html"
    success_url = "@ai.llm_list"
    llm_type = None

    def __init__(self, llm_type, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.llm_type = llm_type

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        kwargs["org"] = self.request.org
        kwargs["llm_type"] = self.llm_type
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_blurb"] = self.llm_type.get_form_blurb()
        return context


class LLMCRUDL(SmartCRUDL):
    model = LLM
    actions = ("list", "update", "translate", "delete")

    class List(SpaMixin, ContextMenuMixin, BaseListView):
        title = _("Artificial Intelligence")
        menu_path = "settings/ai"
        default_order = ("name",)

        def build_context_menu(self, menu):
            if self.has_org_perm("ai.llm_connect") and not self.is_limit_reached():
                menu.add_modax(_("New"), "new-llm", reverse("ai.types.openai.connect"), title="OpenAI", as_button=True)

    class Update(BaseUpdateModal):
        class Form(UniqueNameMixin, forms.ModelForm):
            def __init__(self, org, *args, **kwargs):
                super().__init__(*args, **kwargs)

                self.org = org

            class Meta:
                model = LLM
                fields = ("name",)

        form_class = Form
        slug_url_kwarg = "uuid"
        success_url = "@ai.llm_list"

    class Translate(OrgObjPermsMixin, SmartUpdateView):
        slug_url_kwarg = "uuid"

        @csrf_exempt
        def dispatch(self, *args, **kwargs):
            return super().dispatch(*args, **kwargs)

        def post(self, request, *args, **kwargs):
            self.object = self.get_object()
            data = json.loads(request.body)

            try:
                translated = self.object.translate(data["lang"]["from"], data["lang"]["to"], data["text"])
            except mailroom.AIReasoningException:  # pragma: no cover
                return JsonResponse({"error": "LLM was not able to translate as requested"}, status=400)

            return JsonResponse({"result": translated})

    class Delete(BaseDependencyDeleteModal):
        cancel_url = "@ai.llm_list"
        success_url = "@ai.llm_list"
        success_message = _("Your LLM model has been deleted.")

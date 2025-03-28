import json

from smartmin.views import SmartCRUDL, SmartUpdateView

from django import forms
from django.http import JsonResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt

from temba.orgs.views.base import BaseDependencyDeleteModal, BaseListView, BaseUpdateModal
from temba.orgs.views.mixins import OrgObjPermsMixin
from temba.utils.views.mixins import ContextMenuMixin, SpaMixin

from .models import LLM


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
        class Form(forms.ModelForm):
            def __init__(self, org, *args, **kwargs):
                super().__init__(*args, **kwargs)

                self.org = org

            def clean_name(self):
                name = self.cleaned_data["name"]

                # make sure the name isn't already taken
                conflicts = self.org.llms.filter(name__iexact=name, is_active=True)
                if self.instance:
                    conflicts = conflicts.exclude(id=self.instance.id)

                if conflicts.exists():
                    raise forms.ValidationError(_("Model with this name already exists."))

                return name

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

            return JsonResponse(
                {"result": self.object.translate(data["lang"]["from"], data["lang"]["to"], data["text"])}
            )

    class Delete(BaseDependencyDeleteModal):
        cancel_url = "@ai.llm_list"
        success_url = "@ai.llm_list"
        success_message = _("Your LLM model has been deleted.")

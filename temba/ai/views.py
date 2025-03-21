import json

from smartmin.views import SmartCRUDL, SmartUpdateView

from django.http import JsonResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt

from temba.orgs.views.base import BaseDependencyDeleteModal, BaseListView
from temba.orgs.views.mixins import OrgObjPermsMixin
from temba.utils.views.mixins import ContextMenuMixin, SpaMixin

from .models import LLM


class LLMCRUDL(SmartCRUDL):
    model = LLM
    actions = ("list", "delete", "translate")

    class List(SpaMixin, ContextMenuMixin, BaseListView):
        title = _("AI Models")
        menu_path = "settings/ai"
        fields = ("name", "type", "value")
        default_order = ("name",)
        paginate_by = 250

        def build_context_menu(self, menu):
            if self.has_org_perm("ai.llm_connect"):
                menu.add_modax(
                    _("New"),
                    "new-llm",
                    reverse("ai.types.openai.connect"),
                    title="OpenAI",
                    as_button=True,
                )

    class Delete(BaseDependencyDeleteModal):
        cancel_url = "@ai.llm_list"
        success_url = "@ai.llm_list"
        success_message = _("Your LLM model has been deleted.")

    class Translate(OrgObjPermsMixin, SmartUpdateView):
        permission = "ai.llm_translate"
        slug_url_kwarg = "uuid"

        @csrf_exempt
        def dispatch(self, *args, **kwargs):
            return super().dispatch(*args, **kwargs)

        def post(self, request, *args, **kwargs):
            self.object = self.get_object()

            data = json.loads(request.body)
            text = data["text"]
            lang_from = data["lang"]["from"]
            lang_to = data["lang"]["to"]

            result = self.object.translate(text, lang_from, lang_to)
            return JsonResponse({"result": result})

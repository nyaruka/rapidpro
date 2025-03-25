from smartmin.views import SmartCRUDL

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from temba.orgs.views.base import BaseDependencyDeleteModal, BaseListView
from temba.utils.views.mixins import ContextMenuMixin, SpaMixin

from .models import LLM


class LLMCRUDL(SmartCRUDL):
    model = LLM
    actions = ("list", "delete")

    class List(SpaMixin, ContextMenuMixin, BaseListView):
        title = _("AI Models")
        menu_path = "settings/ai"
        default_order = ("name",)

        def build_context_menu(self, menu):
            if self.has_org_perm("ai.llm_connect") and not self.is_limit_reached():
                menu.add_modax(_("New"), "new-llm", reverse("ai.types.openai.connect"), title="OpenAI", as_button=True)

    class Delete(BaseDependencyDeleteModal):
        cancel_url = "@ai.llm_list"
        success_url = "@ai.llm_list"
        success_message = _("Your LLM model has been deleted.")

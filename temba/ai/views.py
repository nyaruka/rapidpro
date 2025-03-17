from smartmin.views import SmartCRUDL, SmartTemplateView, SmartFormView

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from temba.orgs.views.base import BaseDependencyDeleteModal, BaseReadView
from temba.orgs.views.mixins import OrgPermsMixin
from temba.utils.views.mixins import ComponentFormMixin, ContextMenuMixin, ModalFormMixin, SpaMixin

from .models import LLM


class BaseConnectView(ModalFormMixin, ComponentFormMixin, OrgPermsMixin, SmartFormView):
    permission = "ai.llm_connect"
    llm_type = None
    menu_path = "/settings/ai/new-model"

    def __init__(self, llm_type):
        self.llm_type = llm_type
        super().__init__()

    def get_template_names(self):
        return (
            f"ai/types/{self.llm_type.slug}/connect.html",
            "ai/llm_connect_form.html",
        )

    def get_success_url(self):
        return reverse("ai.llm_read", args=[self.object.uuid])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_blurb"] = self.llm_type.get_form_blurb()
        return context


class LLMCRUDL(SmartCRUDL):
    model = LLM
    actions = ("read", "connect", "delete")

    class Read(SpaMixin, ContextMenuMixin, BaseReadView):
        slug_url_kwarg = "uuid"
        exclude = ("id", "is_active", "created_by", "modified_by", "modified_on")

        def derive_menu_path(self):
            return f"/settings/ai/{self.object.uuid}"

    class Delete(BaseDependencyDeleteModal):
        cancel_url = "uuid@ai.llm_read"
        success_url = "@orgs.org_workspace"
        success_message = _("Your LLM model has been deleted.")

    class Connect(SpaMixin, OrgPermsMixin, SmartTemplateView):
        permission = "ai.llm_connect"
        menu_path = "/settings/ai/new-model"

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context["llm_types"] = [t for t in LLM.get_types()]
            return context

import json

from smartmin.views import SmartCRUDL

from django import forms
from django.db.models import Count
from django.db.models.functions import Lower
from django.http import JsonResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt

from temba import mailroom
from temba.orgs.models import Org
from temba.orgs.views.base import (
    BaseCreateModal,
    BaseDeleteModal,
    BaseDependencyDeleteModal,
    BaseListView,
    BaseMenuView,
    BaseReadView,
    BaseUpdateModal,
)
from temba.orgs.views.mixins import OrgPermsMixin, RequireFeatureMixin, UniqueNameMixin
from temba.utils.fields import InputWidget, SelectWidget
from temba.utils.views.mixins import ContextMenuMixin, PostOnlyMixin, SpaMixin
from temba.utils.views.wizard import SmartWizardView

from .models import LLM, KnowledgeBase


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


class ModelForm(BaseConnectWizard.Form):
    """
    Reusable wizard form for selecting a model.
    """

    model = forms.ChoiceField(
        label=_("Model"), widget=SelectWidget(), help_text=_("Choose the model you would like to use.")
    )

    def __init__(self, model_choices, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["model"].choices = model_choices


class NameForm(BaseConnectWizard.Form):
    """
    Reusable wizard form for giving a name to a model.
    """

    name = forms.CharField(
        label=_("Name"), widget=InputWidget(), help_text=_("Give your model a memorable name."), required=True
    )

    def __init__(self, model_name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["name"].initial = model_name

    def clean_name(self):
        name = self.cleaned_data["name"]

        # make sure the name isn't already taken
        if self.org.llms.filter(is_active=True, name__iexact=name).exists():
            raise forms.ValidationError(_("Must be unique."))

        return name


class LLMCRUDL(SmartCRUDL):
    model = LLM
    actions = ("list", "update", "translate", "delete")

    class List(SpaMixin, ContextMenuMixin, BaseListView):
        title = _("Artificial Intelligence")
        default_order = (Lower("name"),)

        def derive_menu_path(self):
            if Org.FEATURE_AGENTS in self.request.org.features:
                return "/ai/models"
            return "settings/ai"

        def derive_queryset(self, **kwargs):
            return super().derive_queryset(**kwargs).filter(is_system=False)

        def build_context_menu(self, menu):
            if self.has_org_perm("ai.llm_connect") and not self.is_limit_reached():
                org = self.request.org
                user = self.request.user
                for llm_type in LLM.get_types():
                    if not llm_type.is_available_to(org, user):
                        continue
                    menu.add_modax(
                        f"New {llm_type.name}",
                        f"new-{llm_type.slug}",
                        reverse(f"ai.types.{llm_type.slug}.connect"),
                        title=llm_type.name,
                    )

    class Update(BaseUpdateModal):
        class Form(UniqueNameMixin, forms.ModelForm):
            def __init__(self, org, *args, **kwargs):
                super().__init__(*args, **kwargs)

                self.org = org

            class Meta:
                model = LLM
                fields = ("name",)

        form_class = Form
        success_url = "@ai.llm_list"

    class Translate(PostOnlyMixin, BaseReadView):
        @csrf_exempt
        def dispatch(self, *args, **kwargs):
            return super().dispatch(*args, **kwargs)

        def post(self, request, *args, **kwargs):
            self.object = self.get_object()
            data = json.loads(request.body)

            try:
                items = self.object.translate(data["source"], data["target"], data["items"])
            except mailroom.AIServiceException as e:
                return JsonResponse({"error": str(e)}, status=400)

            return JsonResponse({"items": items})

    class Delete(BaseDependencyDeleteModal):
        cancel_url = "@ai.llm_list"
        success_url = "@ai.llm_list"
        success_message = _("Your LLM model has been deleted.")


class AIMenu(BaseMenuView):
    """
    The AI section menu, shown top-level to orgs with the agents feature: the LLM models list and the
    knowledge bases that agents will answer from.
    """

    permission = "ai.llm_list"

    def derive_menu(self):
        org = self.request.org
        menu = [
            self.create_menu_item(
                menu_id="models",
                name=_("Models"),
                icon="ai",
                href="ai.llm_list",
                count=org.llms.filter(is_active=True, is_system=False).count(),
            )
        ]

        if Org.FEATURE_AGENTS in org.features and self.has_org_perm("ai.knowledgebase_list"):
            menu.append(
                self.create_menu_item(
                    menu_id="knowledge",
                    name=_("Knowledge"),
                    icon="browser",
                    href="ai.knowledgebase_list",
                    count=org.knowledge_bases.filter(is_active=True).count(),
                )
            )

        return menu


class WebsiteKnowledgeBaseForm(UniqueNameMixin, forms.ModelForm):
    def __init__(self, org, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.org = org
        self.fields["url"].required = True

    class Meta:
        model = KnowledgeBase
        fields = ("name", "url")
        widgets = {"name": InputWidget(), "url": InputWidget()}
        labels = {"url": _("URL")}
        help_texts = {
            "url": _(
                "The address of the help site to crawl, e.g. https://help.example.com. Articles found there "
                "will be ingested so that agents can answer questions from them."
            )
        }


class NameOnlyKnowledgeBaseForm(UniqueNameMixin, forms.ModelForm):
    def __init__(self, org, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.org = org

    class Meta:
        model = KnowledgeBase
        fields = ("name",)
        widgets = {"name": InputWidget()}


class KnowledgeBaseCRUDL(SmartCRUDL):
    model = KnowledgeBase
    actions = ("list", "create", "read", "delete")

    class List(RequireFeatureMixin, SpaMixin, ContextMenuMixin, BaseListView):
        require_feature = Org.FEATURE_AGENTS
        title = _("Knowledge")
        menu_path = "/ai/knowledge"
        default_order = (Lower("name"),)

        def build_context_menu(self, menu):
            if self.has_org_perm("ai.knowledgebase_create"):
                menu.add_modax(
                    _("New Website"),
                    "new-website",
                    reverse("ai.knowledgebase_create") + "?type=W",
                    title=_("New Website Knowledge Base"),
                    on_submit="refreshMenu()",
                )
                menu.add_modax(
                    _("New Documents"),
                    "new-documents",
                    reverse("ai.knowledgebase_create") + "?type=D",
                    title=_("New Documents Knowledge Base"),
                    on_submit="refreshMenu()",
                )
                menu.add_modax(
                    _("New FAQ"),
                    "new-faq",
                    reverse("ai.knowledgebase_create") + "?type=F",
                    title=_("New FAQ Knowledge Base"),
                    on_submit="refreshMenu()",
                )

    class Create(RequireFeatureMixin, BaseCreateModal):
        require_feature = Org.FEATURE_AGENTS
        title = _("New Knowledge Base")

        def derive_kb_type(self) -> str:
            kb_type = self.request.GET.get("type", KnowledgeBase.TYPE_WEBSITE)
            return kb_type if kb_type in dict(KnowledgeBase.TYPE_CHOICES) else KnowledgeBase.TYPE_WEBSITE

        def get_form_class(self):
            if self.derive_kb_type() == KnowledgeBase.TYPE_WEBSITE:
                return WebsiteKnowledgeBaseForm
            return NameOnlyKnowledgeBaseForm

        def save(self, obj):
            # must set self.object as smartmin ignores the return value and passes self.object to post_save
            org, user, kb_type = self.request.org, self.request.user, self.derive_kb_type()
            if kb_type == KnowledgeBase.TYPE_WEBSITE:
                self.object = KnowledgeBase.create_website(org, user, obj.name, obj.url)
            elif kb_type == KnowledgeBase.TYPE_DOCUMENTS:
                self.object = KnowledgeBase.create_documents(org, user, obj.name)
            else:
                self.object = KnowledgeBase.create_faq(org, user, obj.name)

        def get_success_url(self):
            return reverse("ai.knowledgebase_read", args=[self.object.uuid])

    class Read(RequireFeatureMixin, SpaMixin, ContextMenuMixin, BaseReadView):
        require_feature = Org.FEATURE_AGENTS
        menu_path = "/ai/knowledge"

        def derive_title(self):
            return self.object.name

        def build_context_menu(self, menu):
            obj = self.get_object()  # self.object isn't set when the content menu is fetched
            if self.has_org_perm("ai.knowledgebase_delete"):
                menu.add_modax(
                    _("Delete"),
                    "delete",
                    reverse("ai.knowledgebase_delete", args=[obj.uuid]),
                    title=_("Delete Knowledge Base"),
                )

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            order = "title" if self.object.kb_type == KnowledgeBase.TYPE_FAQ else "-created_on"
            context["articles"] = self.object.articles.annotate(chunk_count=Count("chunks")).order_by(order)[:100]
            return context

    class Delete(RequireFeatureMixin, BaseDeleteModal):
        require_feature = Org.FEATURE_AGENTS
        cancel_url = "@ai.knowledgebase_list"
        redirect_url = "@ai.knowledgebase_list"
        success_message = _("Your knowledge base has been deleted.")

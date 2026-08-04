import magic
from smartmin.views import SmartCRUDL, SmartReadView, SmartTemplateView

from django.db.models.functions import Lower
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from temba.orgs.models import Org
from temba.orgs.views.base import BaseCreateModal, BaseDeleteModal, BaseMenuView, BaseReadView, BaseUpdateModal
from temba.orgs.views.mixins import OrgObjPermsMixin, OrgPermsMixin, RequireFeatureMixin
from temba.utils.views.mixins import ContextMenuMixin, PostOnlyMixin, SpaMixin

from .forms import KnowledgeForm, KnowledgeUpdateForm
from .models import Knowledge, KnowledgeItem


class KnowledgeCRUDL(SmartCRUDL):
    model = Knowledge
    actions = ("menu", "read", "create", "update", "delete", "upload", "shortcuts", "helpdesk")

    class Menu(RequireFeatureMixin, BaseMenuView):
        require_feature = Org.FEATURE_AGENTS

        def derive_menu(self):
            org = self.request.org

            menu = [
                self.create_menu_item(
                    menu_id="shortcuts",
                    name=_("Shortcuts"),
                    icon="shortcut",
                    count=org.shortcuts.filter(is_active=True).count(),
                    href="knowledge.knowledge_shortcuts",
                    perm="knowledge.knowledge_read",
                ),
                self.create_menu_item(
                    menu_id="helpdesk",
                    name=_("Helpdesk"),
                    icon="help",
                    href="knowledge.knowledge_helpdesk",
                    perm="knowledge.knowledge_read",
                ),
            ]

            sources = org.knowledge.filter(is_system=False, is_active=True).order_by(Lower("name"))
            if sources:
                menu.append(self.create_divider())
                for source in sources:
                    menu.append(
                        self.create_menu_item(
                            menu_id=str(source.uuid),
                            name=source.name,
                            icon="website" if source.knowledge_type == Knowledge.TYPE_WEBSITE else "documents",
                            href=reverse("knowledge.knowledge_read", args=[source.uuid]),
                        )
                    )

            if not Knowledge.is_limit_reached(org):
                menu.append(self.create_space())
                menu.append(
                    self.create_modax_button(
                        _("New Source"), "knowledge.knowledge_create", icon="add", on_submit="refreshMenu()"
                    )
                )

            return menu

    class Read(RequireFeatureMixin, SpaMixin, ContextMenuMixin, BaseReadView):
        require_feature = Org.FEATURE_AGENTS

        def derive_menu_path(self):
            return f"/knowledge/{self.object.uuid}"

        def derive_queryset(self, **kwargs):
            # the system shortcuts and helpdesk sources have their own fixed URL pages
            return super().derive_queryset(**kwargs).filter(is_system=False)

        def derive_title(self):
            return self.object.name

        def build_context_menu(self, menu):
            obj = self.get_object()  # self.object isn't set when the content menu is fetched

            if obj.knowledge_type == Knowledge.TYPE_DOCUMENTS and self.has_org_perm("knowledge.knowledge_upload"):
                menu.add_js("uploadKnowledgeItem", _("Upload"), as_button=True)

            if self.has_org_perm("knowledge.knowledge_update"):
                menu.add_modax(
                    _("Edit"),
                    "update-knowledge",
                    reverse("knowledge.knowledge_update", args=[obj.uuid]),
                    title=_("Update Source"),
                )
            if self.has_org_perm("knowledge.knowledge_delete"):
                menu.add_modax(
                    _("Delete"),
                    "delete-knowledge",
                    reverse("knowledge.knowledge_delete", args=[obj.uuid]),
                    title=_("Delete Source"),
                )

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            obj = self.object

            context["is_website"] = obj.knowledge_type == Knowledge.TYPE_WEBSITE
            context["is_documents"] = obj.knowledge_type == Knowledge.TYPE_DOCUMENTS

            if context["is_website"]:
                # pages are mailroom's to write, so there's no upload affordance here - just the list
                context["items"] = obj.items.order_by("name")
            else:
                context["items"] = obj.items.order_by("-created_on")
                context["upload_url"] = reverse("knowledge.knowledge_upload", args=[obj.uuid])
                context["items_limit_reached"] = obj.items.count() >= KnowledgeItem.MAX_DOCUMENTS

            return context

    class Shortcuts(RequireFeatureMixin, SpaMixin, ContextMenuMixin, OrgPermsMixin, SmartTemplateView):
        """
        The org's system shortcuts source at a fixed URL so it can be a menu item.
        """

        require_feature = Org.FEATURE_AGENTS
        permission = "knowledge.knowledge_read"
        title = _("Shortcuts")
        menu_path = "/knowledge/shortcuts"

        def build_context_menu(self, menu):
            if self.has_org_perm("tickets.shortcut_create"):
                menu.add_modax(
                    _("New"),
                    "new-shortcut",
                    reverse("tickets.shortcut_create"),
                    title=_("New Shortcut"),
                    as_button=True,
                )

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)

            obj = self.request.org.knowledge.filter(
                knowledge_type=Knowledge.TYPE_SHORTCUTS, is_system=True, is_active=True
            ).first()
            if not obj:
                raise Http404()

            context["object"] = obj
            context["shortcuts_endpoint"] = f"{reverse('api.internal.shortcuts')}.json"
            return context

    class Helpdesk(RequireFeatureMixin, SpaMixin, OrgPermsMixin, SmartTemplateView):
        """
        The org's system helpdesk source at a fixed URL so it can be a menu item.
        """

        require_feature = Org.FEATURE_AGENTS
        permission = "knowledge.knowledge_read"
        title = _("Helpdesk")
        menu_path = "/knowledge/helpdesk"

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)

            obj = self.request.org.knowledge.filter(
                knowledge_type=Knowledge.TYPE_HELPDESK, is_system=True, is_active=True
            ).first()
            if not obj:
                raise Http404()

            context["object"] = obj
            # phase 1: a flat list in tree order. Phase 4 replaces this with the authoring surface.
            context["articles"] = obj.articles.filter(is_active=True).order_by("parent_id", "sort_order", "title")
            return context

    class Create(RequireFeatureMixin, BaseCreateModal):
        require_feature = Org.FEATURE_AGENTS
        form_class = KnowledgeForm
        title = _("New Source")

        def save(self, obj):
            # must set self.object as smartmin ignores the return value
            org, user, data = self.request.org, self.request.user, self.form.cleaned_data

            if data["knowledge_type"] == Knowledge.TYPE_WEBSITE:
                self.object = Knowledge.create_website(
                    org,
                    user,
                    data["name"],
                    data["url"],
                    max_pages=data.get("max_pages"),
                    refresh=data.get("refresh"),
                )
            else:
                self.object = Knowledge.create_documents(org, user, data["name"])

        def get_success_url(self):
            return reverse("knowledge.knowledge_read", args=[self.object.uuid])

    class Update(RequireFeatureMixin, BaseUpdateModal):
        require_feature = Org.FEATURE_AGENTS
        form_class = KnowledgeUpdateForm

        def pre_save(self, obj):
            obj = super().pre_save(obj)

            if obj.knowledge_type == Knowledge.TYPE_WEBSITE:
                data = self.form.cleaned_data
                new_config = {
                    Knowledge.CONFIG_URL: data["url"],
                    Knowledge.CONFIG_MAX_DEPTH: obj.config.get(Knowledge.CONFIG_MAX_DEPTH, Knowledge.DEFAULT_MAX_DEPTH),
                    Knowledge.CONFIG_MAX_PAGES: data.get("max_pages") or Knowledge.DEFAULT_MAX_PAGES,
                    Knowledge.CONFIG_REFRESH: data.get("refresh") or Knowledge.REFRESH_WEEKLY,
                }
                # anything that changes what gets crawled means it needs reindexing
                if new_config != obj.config:
                    obj.status = Knowledge.STATUS_PENDING
                    obj.error = None
                obj.config = new_config

            return obj

        def get_success_url(self):
            return reverse("knowledge.knowledge_read", args=[self.object.uuid])

    class Delete(RequireFeatureMixin, BaseDeleteModal):
        require_feature = Org.FEATURE_AGENTS
        cancel_url = "@knowledge.knowledge_shortcuts"
        redirect_url = "@knowledge.knowledge_shortcuts"
        success_message = _("Your knowledge source has been deleted.")

    class Upload(RequireFeatureMixin, PostOnlyMixin, OrgObjPermsMixin, SmartReadView):
        """
        Multipart in, JSON out - mirrors msgs.media_upload. Always 200; errors are {"error": "..."}.
        """

        require_feature = Org.FEATURE_AGENTS
        permission = "knowledge.knowledge_upload"
        slug_url_kwarg = "uuid"

        def post(self, request, *args, **kwargs):
            obj = self.get_object()

            # only document sets accept uploads - website pages are mailroom's to create
            if obj.knowledge_type != Knowledge.TYPE_DOCUMENTS:
                return JsonResponse({"error": _("Files can only be added to document sets.")})
            if obj.items.count() >= KnowledgeItem.MAX_DOCUMENTS:
                return JsonResponse({"error": _("Limit of %d documents reached.") % KnowledgeItem.MAX_DOCUMENTS})

            file = request.FILES["file"]
            detected_type = magic.from_buffer(next(file.chunks(chunk_size=2048)), mime=True)

            if not KnowledgeItem.is_allowed_type(detected_type):
                return JsonResponse({"error": _("Unsupported file type")})
            if file.size > KnowledgeItem.MAX_UPLOAD_SIZE:
                limit_MB = KnowledgeItem.MAX_UPLOAD_SIZE / (1024 * 1024)
                return JsonResponse({"error": _("Limit for file uploads is %s MB") % limit_MB})

            file.content_type = detected_type  # trust the sniffed type, not the browser's
            item = KnowledgeItem.from_upload(obj, request.user, file)

            return JsonResponse({"uuid": str(item.uuid), "name": item.name, "size": item.size, "status": "pending"})


class KnowledgeItemCRUDL(SmartCRUDL):
    model = KnowledgeItem
    actions = ("delete",)

    class Delete(RequireFeatureMixin, BaseDeleteModal):
        require_feature = Org.FEATURE_AGENTS
        model_org_lookup = "knowledge__org"
        cancel_url = "@knowledge.knowledge_shortcuts"
        submit_button_name = _("Delete")

        def post(self, request, *args, **kwargs):
            self.object = self.get_object()
            knowledge = self.object.knowledge
            self.object.delete()  # hard delete - purges chunks then the storage object

            return HttpResponseRedirect(reverse("knowledge.knowledge_read", args=[knowledge.uuid]))

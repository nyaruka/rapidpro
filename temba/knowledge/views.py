import magic
from smartmin.views import SmartCRUDL, SmartReadView, SmartTemplateView

from django.db.models.functions import Lower
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from temba.orgs.models import Org
from temba.orgs.views.base import (
    BaseCreateModal,
    BaseDeleteModal,
    BaseMenuView,
    BaseReadView,
    BaseUpdateModal,
    BaseUpdateView,
)
from temba.orgs.views.mixins import OrgObjPermsMixin, OrgPermsMixin, RequireFeatureMixin
from temba.utils import json
from temba.utils.views.mixins import ContextMenuMixin, PostOnlyMixin, SpaMixin

from .forms import ArticleCreateForm, ArticleForm, KnowledgeForm, KnowledgeUpdateForm
from .models import Article, ArticleImage, Knowledge, KnowledgeItem, render_markdown


class KnowledgeCRUDL(SmartCRUDL):
    model = Knowledge
    actions = ("menu", "read", "create", "update", "delete", "upload", "shortcuts")

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
                    href="knowledge.article_list",
                    perm="knowledge.article_list",
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


class HelpdeskMixin(RequireFeatureMixin):
    """
    Common to every article view: the agents feature gate, and the org's system helpdesk source, which is the only
    place articles can live - so it's resolved here rather than taken from the URL.
    """

    require_feature = Org.FEATURE_AGENTS

    @cached_property
    def helpdesk(self):
        obj = self.request.org.knowledge.filter(
            knowledge_type=Knowledge.TYPE_HELPDESK, is_system=True, is_active=True
        ).first()
        if not obj:
            raise Http404()
        return obj


class ArticleCRUDL(SmartCRUDL):
    model = Article
    actions = ("list", "read", "create", "update", "delete", "sort", "publish", "unpublish", "preview", "upload")

    class BasePage(HelpdeskMixin, SpaMixin):
        """
        The pages of the authoring surface, all of which render the article tree alongside their own content.
        """

        menu_path = "/knowledge/helpdesk"

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context["helpdesk"] = self.helpdesk
            context["tree"] = Article.get_tree(self.helpdesk)
            context["max_depth"] = Article.MAX_DEPTH
            context["sort_url"] = reverse("knowledge.article_sort")
            context["can_sort"] = self.has_org_perm("knowledge.article_sort")
            return context

    class BaseObject(HelpdeskMixin):
        """
        Scopes a view of a single article to this org's helpdesk.
        """

        slug_url_kwarg = "uuid"
        model_org_lookup = "knowledge__org"

        def derive_queryset(self, **kwargs):
            return super().derive_queryset(**kwargs).filter(knowledge=self.helpdesk)

    class List(BasePage, ContextMenuMixin, OrgPermsMixin, SmartTemplateView):
        """
        The helpdesk itself - the article tree with nothing selected.
        """

        title = _("Helpdesk")

        def build_context_menu(self, menu):
            if self.has_org_perm("knowledge.article_create"):
                menu.add_modax(
                    _("New"),
                    "new-article",
                    reverse("knowledge.article_create"),
                    title=_("New Article"),
                    as_button=True,
                )

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context["object"] = self.helpdesk
            return context

    class Read(BaseObject, BasePage, ContextMenuMixin, BaseReadView):
        """
        An article as readers will see it - the sanitized render of its markdown.
        """

        def derive_title(self):
            return self.object.title

        def build_context_menu(self, menu):
            obj = self.get_object()  # self.object isn't set when the content menu is fetched

            if self.has_org_perm("knowledge.article_update"):
                menu.add_link(_("Edit"), reverse("knowledge.article_update", args=[obj.uuid]))

            if obj.status == Article.STATUS_DRAFT:
                if self.has_org_perm("knowledge.article_publish"):
                    menu.add_url_post(_("Publish"), reverse("knowledge.article_publish", args=[obj.uuid]))
            elif self.has_org_perm("knowledge.article_unpublish"):
                menu.add_url_post(_("Unpublish"), reverse("knowledge.article_unpublish", args=[obj.uuid]))

            if self.has_org_perm("knowledge.article_delete"):
                menu.add_modax(
                    _("Delete"),
                    "delete-article",
                    reverse("knowledge.article_delete", args=[obj.uuid]),
                    title=_("Delete Article"),
                )

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context["rendered"] = self.object.as_html()
            context["selected"] = str(self.object.uuid)
            return context

    class Create(HelpdeskMixin, BaseCreateModal):
        form_class = ArticleCreateForm
        title = _("New Article")

        def get_blocker(self) -> str:
            if self.helpdesk.articles.filter(is_active=True).count() >= Article.MAX_ARTICLES:
                return "limit_reached"
            return ""

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context["blocker"] = self.get_blocker()
            context["max_articles"] = Article.MAX_ARTICLES
            return context

        def form_valid(self, form):
            if self.get_blocker():
                return self.form_invalid(form)
            return super().form_valid(form)

        def pre_save(self, obj):
            return obj  # articles belong to a helpdesk rather than directly to the org

        def save(self, obj):
            # must set self.object as smartmin ignores the return value
            self.object = Article.create(
                self.helpdesk, self.request.user, obj.title, language=self.form.cleaned_data.get("language")
            )

        def get_success_url(self):
            # straight into the editor - a new article has nothing to read yet
            return reverse("knowledge.article_update", args=[self.object.uuid])

    class Update(BaseObject, BasePage, ContextMenuMixin, BaseUpdateView):
        """
        The editor - a full page rather than a modal, because an article body needs the room.
        """

        form_class = ArticleForm
        success_message = ""

        def derive_title(self):
            return self.object.title

        def get_form_kwargs(self):
            kwargs = super().get_form_kwargs()
            kwargs["org"] = self.request.org
            return kwargs

        def get_form(self):
            form = super().get_form()

            # the editor uploads screenshots and renders its preview against this article
            form.fields["body"].widget.attrs.update(
                {
                    "endpoint": reverse("knowledge.article_upload", args=[self.get_object().uuid]),
                    "preview_endpoint": reverse("knowledge.article_preview"),
                    "accept": ",".join(ArticleImage.ALLOWED_CONTENT_TYPES),
                }
            )
            return form

        def build_context_menu(self, menu):
            menu.add_link(_("View"), reverse("knowledge.article_read", args=[self.get_object().uuid]))

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context["selected"] = str(self.object.uuid)
            return context

        def pre_save(self, obj):
            obj = super().pre_save(obj)

            # the title is the article's identity on the eventual public site, so the slug follows it
            obj.slug = Article.get_unique_slug(obj.knowledge, obj.title, ignore=obj)
            return obj

        def get_success_url(self):
            return reverse("knowledge.article_read", args=[self.object.uuid])

    class Delete(BaseObject, BaseDeleteModal):
        cancel_url = "@knowledge.article_list"
        redirect_url = "@knowledge.article_list"
        submit_button_name = _("Delete")

        def get_queryset(self, **kwargs):
            return super().get_queryset(**kwargs).filter(knowledge=self.helpdesk)

    class Publish(BaseObject, PostOnlyMixin, OrgObjPermsMixin, SmartReadView):
        """
        Makes an article live, and therefore indexable. Explicit rather than a field on the editor form, so that saving
        an edit can never make a draft public by accident.
        """

        def post(self, request, *args, **kwargs):
            self.object = self.get_object()
            self.object.publish(request.user)

            return HttpResponseRedirect(reverse("knowledge.article_read", args=[self.object.uuid]))

    class Unpublish(BaseObject, PostOnlyMixin, OrgObjPermsMixin, SmartReadView):
        """
        Returns an article to draft. Its modified_on bumps, so mailroom's next sweep drops its chunks.
        """

        def post(self, request, *args, **kwargs):
            self.object = self.get_object()
            self.object.unpublish(request.user)

            return HttpResponseRedirect(reverse("knowledge.article_read", args=[self.object.uuid]))

    class Sort(HelpdeskMixin, PostOnlyMixin, OrgPermsMixin, SmartTemplateView):
        """
        Applies a new tree ordering, posted as (uuid, parent, sort_order) triples. The client's tree is never trusted -
        the model re-derives the resulting forest and rejects it if it isn't one.
        """

        def post(self, request, *args, **kwargs):
            try:
                payload = json.loads(request.body)
                if len(payload) > Article.MAX_ARTICLES:
                    raise ValueError("too many entries")

                # sort orders are clamped rather than trusted - JSON numbers are unbounded, so an enormous one is
                # either an OverflowError here or an integer out of range at the database
                order = [
                    (
                        str(i["uuid"]),
                        i["parent"] and str(i["parent"]),
                        max(0, min(int(i["sort_order"]), Article.MAX_ARTICLES)),
                    )
                    for i in payload
                ]
            except ValueError, TypeError, KeyError, OverflowError:
                return JsonResponse({"error": _("Invalid ordering.")}, status=400)

            try:
                Article.apply_sort(self.helpdesk, order)
            except ValueError as e:
                return JsonResponse({"error": str(e)}, status=400)

            return JsonResponse({"status": "ok"})

    class Preview(HelpdeskMixin, PostOnlyMixin, OrgPermsMixin, SmartTemplateView):
        """
        Renders markdown for the editor's preview pane. It goes through the server so that it uses the same sanitizing
        renderer as the read page - authors see exactly what will be published, and never their own raw HTML.
        """

        def post(self, request, *args, **kwargs):
            return JsonResponse({"html": render_markdown(request.POST.get("body", "")[: Article.MAX_BODY_LEN])})

    class Upload(BaseObject, PostOnlyMixin, OrgObjPermsMixin, SmartReadView):
        """
        A screenshot for an article body. Multipart in, JSON out - always 200, errors are {"error": "..."}. The image
        goes to public storage because the eventual standalone help site will serve these directly.
        """

        def post(self, request, *args, **kwargs):
            obj = self.get_object()

            if obj.images.count() >= ArticleImage.MAX_IMAGES:
                return JsonResponse({"error": _("Limit of %d images reached.") % ArticleImage.MAX_IMAGES})

            file = request.FILES["file"]
            detected_type = magic.from_buffer(next(file.chunks(chunk_size=2048)), mime=True)

            if not ArticleImage.is_allowed_type(detected_type):
                return JsonResponse({"error": _("Unsupported file type")})
            if file.size > ArticleImage.MAX_UPLOAD_SIZE:
                limit_MB = ArticleImage.MAX_UPLOAD_SIZE / (1024 * 1024)
                return JsonResponse({"error": _("Limit for file uploads is %s MB") % limit_MB})

            file.content_type = detected_type  # trust the sniffed type, not the browser's
            image = ArticleImage.from_upload(obj, request.user, file)

            return JsonResponse({"uuid": str(image.uuid), "name": image.name, "url": image.url})

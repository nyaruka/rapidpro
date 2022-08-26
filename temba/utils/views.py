import logging
from urllib.parse import quote

from django import forms
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from temba.utils.fields import CheckboxWidget, InputWidget, SelectMultipleWidget, SelectWidget

logger = logging.getLogger(__name__)


class SpaMixin(View):
    """
    Uses SPA base template if the header is set appropriately
    """

    @cached_property
    def spa_path(self) -> tuple:
        return tuple(s for s in self.request.META.get("HTTP_TEMBA_PATH", "").split("/") if s)

    @cached_property
    def spa_referrer_path(self) -> tuple:
        return tuple(s for s in self.request.META.get("HTTP_TEMBA_REFERER_PATH", "").split("/") if s)

    def is_spa(self):
        return "HTTP_TEMBA_SPA" in self.request.META

    def get_template_names(self):
        templates = super().get_template_names()
        spa_templates = []

        if self.is_spa():
            for template in templates:
                original = template.split(".")
                if len(original) == 2:
                    spa_template = original[0] + "_spa." + original[1]
                if spa_template:
                    spa_templates.append(spa_template)
        return spa_templates + templates

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.is_spa():
            context["base_template"] = "spa.html"
            context["is_spa"] = True
            context["temba_path"] = self.spa_path
            context["temba_referer"] = self.spa_referrer_path

        return context


class ComponentFormMixin(View):
    """
    Mixin to replace form field controls with component based widgets
    """

    def customize_form_field(self, name, field):
        attrs = field.widget.attrs if field.widget.attrs else {}

        # don't replace the widget if it is already one of us
        if isinstance(
            field.widget, (forms.widgets.HiddenInput, CheckboxWidget, InputWidget, SelectWidget, SelectMultipleWidget)
        ):
            return field

        if isinstance(field.widget, (forms.widgets.Textarea,)):
            attrs["textarea"] = True
            field.widget = InputWidget(attrs=attrs)
        elif isinstance(field.widget, (forms.widgets.PasswordInput,)):  # pragma: needs cover
            attrs["password"] = True
            field.widget = InputWidget(attrs=attrs)
        elif isinstance(
            field.widget,
            (forms.widgets.TextInput, forms.widgets.EmailInput, forms.widgets.URLInput, forms.widgets.NumberInput),
        ):
            field.widget = InputWidget(attrs=attrs)
        elif isinstance(field.widget, (forms.widgets.Select,)):
            if isinstance(field, (forms.models.ModelMultipleChoiceField,)):
                field.widget = SelectMultipleWidget(attrs)  # pragma: needs cover
            else:
                field.widget = SelectWidget(attrs)

            field.widget.choices = field.choices
        elif isinstance(field.widget, (forms.widgets.CheckboxInput,)):
            field.widget = CheckboxWidget(attrs)

        return field


class StaffOnlyMixin:
    """
    Views that only staff should be able to access
    """

    def has_permission(self, request, *args, **kwargs):
        return self.request.user.is_staff


class PostOnlyMixin(View):
    """
    Utility mixin to make a class based view be POST only
    """

    def get(self, *args, **kwargs):
        return HttpResponse("Method Not Allowed", status=405)


class NonAtomicMixin(View):
    """
    Utility mixin to disable automatic transaction wrapping of a class based view
    """

    @transaction.non_atomic_requests
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class BulkActionMixin:
    """
    Mixin for list views which have bulk actions
    """

    bulk_actions = ()
    bulk_action_permissions = {}

    class Form(forms.Form):
        def __init__(self, actions, queryset, label_queryset, *args, **kwargs):
            super().__init__(*args, **kwargs)

            self.fields["action"] = forms.ChoiceField(choices=[(a, a) for a in actions], required=True)
            self.fields["objects"] = forms.ModelMultipleChoiceField(queryset=queryset, required=False)
            self.fields["all"] = forms.BooleanField(required=False)

            if label_queryset:
                self.fields["label"] = forms.ModelChoiceField(label_queryset, required=False)

        def clean(self):
            cleaned_data = super().clean()

            action = cleaned_data.get("action")
            label = cleaned_data.get("label")
            if action in ("label", "unlabel") and not label:
                raise forms.ValidationError("Must specify a label")

            # TODO update frontend to send back unlabel actions
            if action == "label" and self.data.get("add", "").lower() == "false":
                cleaned_data["action"] = "unlabel"

        class Meta:
            fields = ("action", "objects")

    def post(self, request, *args, **kwargs):
        """
        Handles a POSTed action form and returns the default GET response
        """
        user = self.get_user()
        org = user.get_org()
        form = BulkActionMixin.Form(
            self.get_bulk_actions(), self.get_queryset(), self.get_bulk_action_labels(), data=self.request.POST
        )
        action_error = None

        if form.is_valid():
            action = form.cleaned_data["action"]
            objects = form.cleaned_data["objects"]
            all_objects = form.cleaned_data["all"]
            label = form.cleaned_data.get("label")

            if all_objects:
                objects = self.get_queryset()
            else:
                objects_ids = [o.id for o in objects]
                self.kwargs["bulk_action_ids"] = objects_ids  # include in kwargs so is accessible in get call below

                # convert objects queryset to one based only on org + ids
                objects = self.model._default_manager.filter(org=org, id__in=objects_ids)

            # check we have the required permission for this action
            permission = self.get_bulk_action_permission(action)
            if not user.has_perm(permission) and not user.has_org_perm(org, permission):
                return HttpResponseForbidden()

            try:
                self.apply_bulk_action(user, action, objects, label)
            except forms.ValidationError as e:
                action_error = ", ".join(e.messages)
            except Exception:
                logger.exception(f"error applying '{action}' to {self.model.__name__} objects")
                action_error = _("An error occurred while making your changes. Please try again.")

        response = self.get(request, *args, **kwargs)
        if action_error:
            response["Temba-Toast"] = action_error

        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["actions"] = self.get_bulk_actions()
        return context

    def get_bulk_actions(self):
        """
        Gets the allowed bulk actions for this view
        """
        return self.bulk_actions

    def get_bulk_action_permission(self, action):
        """
        Gets the required permission for the given action (defaults to the update permission for the model class)
        """
        default = f"{self.model._meta.app_label}.{self.model.__name__.lower()}_update"

        return self.bulk_action_permissions.get(action, default)

    def get_bulk_action_labels(self):
        """
        Views can override this to provide a set of labels for label/unlabel actions
        """
        return None

    def apply_bulk_action(self, user, action, objects, label):
        """
        Applies the given action to the given objects. If this method throws a validation error, that will become the
        error message sent back to the user.
        """
        func_name = f"apply_action_{action}"
        model_func = getattr(self.model, func_name)
        assert model_func, f"{self.model.__name__} has no method called {func_name}"

        args = [label] if label else []

        model_func(user, objects, *args)


class RequireRecentAuthMixin:
    """
    Mixin that redirects the user to a authentication page if they haven't authenticated recently.
    """

    recent_auth_seconds = 10 * 60
    recent_auth_includes_formax = False

    def pre_process(self, request, *args, **kwargs):
        is_formax = "HTTP_X_FORMAX" in request.META
        if not is_formax or self.recent_auth_includes_formax:
            last_auth_on = request.user.settings.last_auth_on
            if not last_auth_on or (timezone.now() - last_auth_on).total_seconds() > self.recent_auth_seconds:
                return HttpResponseRedirect(reverse("users.confirm_access") + f"?next={quote(request.path)}")

        return super().pre_process(request, *args, **kwargs)


class ExternalURLHandler(View):
    """
    It's useful to register Courier and Mailroom URLs in RapidPro so they can be used in templates, and if they are hit
    here, we can provide the user with a error message about
    """

    service = None

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        logger.error(f"URL intended for {self.service} reached RapidPro", extra={"URL": request.get_full_path()})
        return HttpResponse(f"this URL should be mapped to a {self.service} instance", status=404)


class CourierURLHandler(ExternalURLHandler):
    service = "Courier"


class MailroomURLHandler(ExternalURLHandler):
    service = "Mailroom"


class ContentMenu:
    """
    Utility for building content menus
    """

    def __init__(self):
        self.groups = [[]]

    def new_group(self):
        self.groups.append([])

    def add_link(self, label: str, url: str):
        self.groups[-1].append({"type": "link", "label": label, "url": url})

    def add_js(self, label: str, on_click: str, link_class: str):
        self.groups[-1].append({"type": "js", "label": label, "on_click": on_click, "link_class": link_class})

    def add_url_post(self, label: str, url: str):
        self.groups[-1].append({"type": "url_post", "label": label, "url": url})

    def add_modax(
        self, label: str, modal_id: str, url: str, *, title: str = None, on_submit: str = None, primary: bool = False
    ):
        self.groups[-1].append(
            {
                "type": "modax",
                "label": label,
                "url": url,
                "modal_id": modal_id,
                "title": title or label,
                "on_submit": on_submit,
                "primary": primary,
            }
        )

    def as_items(self):
        """
        Reduce groups to a flat list of items separated by dividers.
        """
        items = []
        for group in self.groups:
            if not group:
                continue
            if items:
                items.append({"type": "divider"})
            items.extend(group)
        return items


class ContentMenuMixin:
    """
    Mixin for views that have a content menu (hamburger icon with dropdown items)

    TODO: use component to read menu as JSON and then can stop putting menu (in legacy gear-links format) in context
    """

    # renderers to convert menu items to the legacy "gear-links" format
    gear_link_renderers = {
        "link": lambda i: {"title": i["label"], "href": i["url"]},
        "js": lambda i: {"title": i["label"], "on_click": i["on_click"], "js_class": i["link_class"], "href": "#"},
        "url_post": lambda i: {"title": i["label"], "href": i["url"], "js_class": "posterize"},
        "modax": lambda i: {
            "id": i["modal_id"],
            "title": i["label"],
            "modax": i["title"],
            "href": i["url"],
            "on_submit": i["on_submit"],
            "style": "button-primary" if i["primary"] else "",
        },
        "divider": lambda i: {"divider": True},
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["gear_links"] = [self.gear_link_renderers[i["type"]](i) for i in self._get_content_menu()]
        return context

    def _get_content_menu(self):
        menu = ContentMenu()
        self.build_content_menu(menu)
        return menu.as_items()

    def build_content_menu(self, menu: ContentMenu):  # pragma: no cover
        pass

    def get(self, request, *args, **kwargs):
        if "HTTP_TEMBA_CONTENT_MENU" in self.request.META:
            return JsonResponse({"items": self._get_content_menu()})

        return super().get(request, *args, **kwargs)

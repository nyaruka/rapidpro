from gettext import gettext as _

from smartmin.views import SmartCreateView, SmartCRUDL, SmartListView, SmartUpdateView

from django import forms
from django.http import JsonResponse
from django.urls import reverse

from temba.orgs.models import Org
from temba.orgs.views import DependencyDeleteModal, DependencyUsagesModal, ModalMixin, OrgObjPermsMixin, OrgPermsMixin
from temba.utils.fields import InputWidget

from .models import Global


class GlobalForm(forms.ModelForm):
    def __init__(self, org, *args, **kwargs):
        self.org = org

        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data["name"]

        if self.org.globals.filter(is_active=True, name__iexact=name).exists():
            raise forms.ValidationError(_("Must be unique."))

        return name

    def clean_key(self):
        key = self.cleaned_data["key"]

        if self.org.globals.filter(is_active=True, key=key).exists():
            raise forms.ValidationError(_("Must be unique."))

        return key

    def clean(self):
        cleaned_data = super().clean()

        global_limit = self.org.get_limit(Org.LIMIT_GLOBALS)
        if self.org.globals.filter(is_active=True).count() >= global_limit:
            raise forms.ValidationError(
                _("Cannot create a new global as limit is %(limit)s."), params={"limit": global_limit}
            )

        return cleaned_data

    class Meta:
        model = Global
        fields = ("name", "key", "value")
        help_texts = {"key": _("How it will be referred to in flows.")}
        widgets = {
            "name": InputWidget(attrs={"name": _("Name"), "widget_only": False}),
            "key": InputWidget(attrs={"name": _("Key"), "widget_only": False, "disabled": True}),
            "value": InputWidget(attrs={"name": _("Value"), "widget_only": False, "textarea": True}),
        }


class GlobalCRUDL(SmartCRUDL):
    model = Global
    actions = ("create", "update", "delete", "list", "unused", "usages")

    class Create(ModalMixin, OrgPermsMixin, SmartCreateView):
        form_class = GlobalForm
        success_message = ""
        submit_button_name = _("Create")

        def get_form_kwargs(self):
            kwargs = super().get_form_kwargs()
            kwargs["org"] = self.derive_org()
            return kwargs

        def derive_initial(self):
            return {"name": "API Key", "key": "api_key"}

        def form_valid(self, form):
            self.object = Global.create(
                self.request.user.get_org(),
                self.request.user,
                name=form.cleaned_data["name"],
                value=form.cleaned_data["value"],
            )

            return self.render_modal_response(form)

    class Update(ModalMixin, OrgObjPermsMixin, SmartUpdateView):
        form_class = GlobalForm
        success_message = ""
        submit_button_name = _("Update")

        def get_form_kwargs(self):
            kwargs = super().get_form_kwargs()
            kwargs["org"] = self.derive_org()
            return kwargs

    class Delete(DependencyDeleteModal):
        cancel_url = "@globals.global_list"
        success_url = "@globals.global_list"
        success_message = ""

    class List(OrgPermsMixin, SmartListView):
        title = _("Manage Globals")
        fields = ("name", "key", "value")
        search_fields = ("name__icontains", "key__icontains")
        default_order = ("key",)
        paginate_by = 250

        def get_queryset(self, **kwargs):
            qs = super().get_queryset(**kwargs).filter(org=self.org, is_active=True)
            return Global.annotate_usage(qs)

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)

            org_globals = self.org.globals.filter(is_active=True)
            all_count = org_globals.count()

            if "HTTP_X_FORMAX" in self.request.META:
                context["global_count"] = all_count
            else:
                unused_count = Global.annotate_usage(org_globals).filter(usage_count=0).count()

                context["global_categories"] = [
                    {"label": _("All"), "count": all_count, "url": reverse("globals.global_list")},
                    {"label": _("Unused"), "count": unused_count, "url": reverse("globals.global_unused")},
                ]

            return context

    class Unused(List):
        def get_queryset(self, **kwargs):
            return super().get_queryset(**kwargs).filter(usage_count=0)

    class Usages(DependencyUsagesModal):
        permission = "globals.global_read"


def name_to_key(request):
    return JsonResponse({"key": Global.name_to_key(request.GET.get("name", ""))})

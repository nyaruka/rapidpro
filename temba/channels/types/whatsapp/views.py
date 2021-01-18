import logging

import requests
from smartmin.views import SmartFormView, SmartReadView, SmartUpdateView

from django import forms
from django.core.validators import validate_image_file_extension
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from temba.contacts.models import URN
from temba.orgs.views import OrgPermsMixin
from temba.request_logs.models import HTTPLog
from temba.templates.models import TemplateTranslation
from temba.utils.fields import ExternalURLField, InputWidget, SelectWidget
from temba.utils.views import PostOnlyMixin

from ...models import Channel
from ...views import ALL_COUNTRIES, ClaimViewMixin
from .tasks import refresh_whatsapp_contacts

logger = logging.getLogger(__name__)


class RefreshView(PostOnlyMixin, OrgPermsMixin, SmartUpdateView):
    """
    Responsible for firing off our contact refresh task
    """

    model = Channel
    fields = ()
    success_message = _("Contacts refresh begun, it may take a few minutes to complete.")
    success_url = "uuid@channels.channel_configuration"
    permission = "channels.channel_claim"
    slug_url_kwarg = "uuid"

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(org=self.get_user().get_org())

    def post_save(self, obj):
        refresh_whatsapp_contacts.delay(obj.id)
        return obj


class DetailsView(OrgPermsMixin, SmartReadView):
    model = Channel
    fields = None
    permission = "channels.channel_read"
    slug_url_kwarg = "uuid"
    template_name = "channels/types/whatsapp/details.html"

    def get_gear_links(self):
        return [
            dict(title=_("Channel Page"), href=reverse("channels.channel_read", args=[self.object.uuid])),
            dict(
                title=_("Update Profile About"), href=reverse("channels.types.whatsapp.about", args=[self.object.uuid])
            ),
            dict(
                title=_("Update Profile Photo"), href=reverse("channels.types.whatsapp.photo", args=[self.object.uuid])
            ),
            dict(
                title=_("Update Business Profile"),
                href=reverse("channels.types.whatsapp.business_profile", args=[self.object.uuid]),
            ),
        ]

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(org=self.get_user().get_org())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["about"] = self.object.get_type().profile_about(self.object)
        context["photo_url"] = self.object.get_type().profile_photo_url(self.object)
        context["business_profile"] = self.object.get_type().business_profile(self.object)

        return context


class UpdateAboutView(OrgPermsMixin, SmartUpdateView):
    class AboutForm(forms.ModelForm):
        about = forms.CharField(required=False, max_length=139, widget=InputWidget())

        class Meta:
            fields = ("about",)
            model = Channel

    model = Channel
    form_class = AboutForm
    success_message = _("Profile about updated successfully.")
    success_url = "uuid@channels.types.whatsapp.details"
    permission = "channels.channel_claim"
    slug_url_kwarg = "uuid"
    template_name = "channels/types/whatsapp/about.html"

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(org=self.get_user().get_org())

    def derive_initial(self):
        initial = super().derive_initial()
        about = self.object.get_type().profile_about(self.object)
        if about:
            initial["about"] = about

        return initial

    def form_valid(self, form):
        try:
            self.object.get_type().set_profile_about(self.object, form.cleaned_data["about"])
            return super().form_valid(form)
        except Exception as e:
            self.form.add_error(
                "about", forms.ValidationError(_("Error setting about, please try again later"), code="about")
            )
            # ensure exception still goes to Sentry
            logger.error("Error setting about: %s" % str(e), exc_info=True)
            return self.form_invalid(form)


class UpdateProfilePhotoView(OrgPermsMixin, SmartUpdateView):
    class PhotoForm(forms.ModelForm):
        photo = forms.ImageField(required=False, validators=[validate_image_file_extension])

        class Meta:
            fields = ("photo",)
            model = Channel

    model = Channel
    form_class = PhotoForm
    success_message = _("Profile photo updated successfully.")
    success_url = "uuid@channels.types.whatsapp.details"
    permission = "channels.channel_claim"
    slug_url_kwarg = "uuid"
    template_name = "channels/types/whatsapp/photo.html"

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(org=self.get_user().get_org())

    def form_valid(self, form):
        try:
            self.object.get_type().set_profile_photo(self.object, form.cleaned_data["photo"])
            return HttpResponseRedirect(self.get_success_url())
        except Exception as e:
            self.form.add_error(
                "photo", forms.ValidationError(_("Error setting photo, please try again later "), code="photo")
            )
            # ensure exception still goes to Sentry
            logger.error("Error setting photo: %s" % str(e), exc_info=True)
            return self.form_invalid(form)


class UpdateBusinessProfileView(OrgPermsMixin, SmartUpdateView):
    class BusinessProfileForm(forms.ModelForm):
        address = forms.CharField(required=False, max_length=256, widget=InputWidget())
        description = forms.CharField(required=False, max_length=256, widget=forms.Textarea)
        email = forms.EmailField(required=False, max_length=128, widget=InputWidget())
        vertical = forms.CharField(required=False, max_length=128, widget=InputWidget())
        website1 = forms.URLField(required=False, max_length=256, widget=InputWidget())
        website2 = forms.URLField(required=False, max_length=256, widget=InputWidget())

        class Meta:
            fields = ("address", "description", "email", "vertical", "website1", "website2")
            model = Channel

    model = Channel
    form_class = BusinessProfileForm
    success_message = _("Business profile update successfully.")
    success_url = "uuid@channels.types.whatsapp.details"
    permission = "channels.channel_claim"
    slug_url_kwarg = "uuid"
    template_name = "channels/types/whatsapp/business_profile.html"

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(org=self.get_user().get_org())

    def derive_initial(self):
        initial = super().derive_initial()
        business_profile = self.object.get_type().business_profile(self.object)

        if business_profile:
            initial["address"] = business_profile.get("address", "")
            initial["description"] = business_profile.get("description", "")
            initial["email"] = business_profile.get("email", "")
            initial["vertical"] = business_profile.get("vertical", "")
            initial["website1"] = business_profile.get("websites", ["", ""])[0]
            initial["website2"] = business_profile.get("websites", ["", ""])[1]
        return initial

    def form_valid(self, form):
        try:
            existing_business_profile = self.object.get_type().business_profile(self.object) or dict()

            updates = dict(websites=[])
            for key in form.cleaned_data.keys():
                if key in ("address", "description", "email", "vertical") and existing_business_profile.get(
                    key, ""
                ) != form.cleaned_data.get(key, ""):
                    updates[key] = form.cleaned_data.get(key, "")
                elif key in ("website1", "website2") and form.cleaned_data.get(key, ""):
                    updates["websites"].append(form.cleaned_data.get(key))

            self.object.get_type().set_business_profile(self.object, updates)
            return HttpResponseRedirect(self.get_success_url())
        except Exception as e:
            self.form.add_error(
                None,
                forms.ValidationError(
                    f"Error setting business profile, please try again later", code="business_profile"
                ),
            )
            # ensure exception still goes to Sentry
            logger.error("Error setting business profile: %s" % str(e), exc_info=True)
            return self.form_invalid(form)


class TemplatesView(OrgPermsMixin, SmartReadView):
    """
    Displays a simple table of all the templates synced on this whatsapp channel
    """

    model = Channel
    fields = ()
    permission = "channels.channel_read"
    slug_url_kwarg = "uuid"
    template_name = "channels/types/whatsapp/templates.html"

    def get_gear_links(self):
        return [dict(title=_("Sync Logs"), href=reverse("channels.types.whatsapp.sync_logs", args=[self.object.uuid]))]

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(org=self.get_user().get_org())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # include all our templates as well
        context["translations"] = TemplateTranslation.objects.filter(channel=self.object).order_by("template__name")
        return context


class SyncLogsView(OrgPermsMixin, SmartReadView):
    """
    Displays a simple table of the WhatsApp Templates Synced requests for this channel
    """

    model = Channel
    fields = ()
    permission = "channels.channel_read"
    slug_url_kwarg = "uuid"
    template_name = "channels/types/whatsapp/sync_logs.html"

    def get_gear_links(self):
        return [
            dict(
                title=_("Message Templates"),
                href=reverse("channels.types.whatsapp.templates", args=[self.object.uuid]),
            )
        ]

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(org=self.get_user().get_org())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # include all our http sync logs as well
        context["sync_logs"] = (
            HTTPLog.objects.filter(
                log_type__in=[
                    HTTPLog.WHATSAPP_TEMPLATES_SYNCED,
                    HTTPLog.WHATSAPP_TOKENS_SYNCED,
                    HTTPLog.WHATSAPP_CONTACTS_REFRESHED,
                ],
                channel=self.object,
            )
            .order_by("-created_on")
            .prefetch_related("channel")
        )
        return context


class ClaimView(ClaimViewMixin, SmartFormView):
    class Form(ClaimViewMixin.Form):
        number = forms.CharField(help_text=_("Your enterprise WhatsApp number"))
        country = forms.ChoiceField(
            widget=SelectWidget(attrs={"searchable": True}),
            choices=ALL_COUNTRIES,
            label=_("Country"),
            help_text=_("The country this phone number is used in"),
        )
        base_url = ExternalURLField(help_text=_("The base URL for your WhatsApp enterprise installation"))
        username = forms.CharField(
            max_length=32, help_text=_("The username to access your WhatsApp enterprise account")
        )
        password = forms.CharField(
            max_length=64, help_text=_("The password to access your WhatsApp enterprise account")
        )

        facebook_template_list_domain = forms.CharField(
            label=_("Templates Domain"),
            help_text=_("Which domain to retrieve the message templates from"),
            initial="graph.facebook.com",
        )

        facebook_business_id = forms.CharField(
            max_length=128, help_text=_("The Facebook waba-id that will be used for template syncing")
        )

        facebook_access_token = forms.CharField(
            max_length=256, help_text=_("The Facebook access token that will be used for syncing")
        )

        facebook_namespace = forms.CharField(max_length=128, help_text=_("The namespace for your WhatsApp templates"))

        def clean(self):
            # first check that our phone number looks sane
            country = self.cleaned_data["country"]
            normalized = URN.normalize_number(self.cleaned_data["number"], country)
            if not URN.validate(URN.from_parts(URN.TEL_SCHEME, normalized), country):
                raise forms.ValidationError(_("Please enter a valid phone number"))
            self.cleaned_data["number"] = normalized

            try:
                resp = requests.post(
                    self.cleaned_data["base_url"] + "/v1/users/login",
                    auth=(self.cleaned_data["username"], self.cleaned_data["password"]),
                )

                if resp.status_code != 200:
                    raise Exception("Received non-200 response: %d", resp.status_code)

                self.cleaned_data["auth_token"] = resp.json()["users"][0]["token"]

            except Exception:
                raise forms.ValidationError(
                    _("Unable to check WhatsApp enterprise account, please check username and password")
                )

            # check we can access their facebook templates
            from .type import TEMPLATE_LIST_URL

            if self.cleaned_data["facebook_template_list_domain"] != "graph.facebook.com":
                response = requests.get(
                    TEMPLATE_LIST_URL
                    % (self.cleaned_data["facebook_template_list_domain"], self.cleaned_data["facebook_business_id"]),
                    params=dict(access_token=self.cleaned_data["facebook_access_token"]),
                )

                if response.status_code != 200:
                    raise forms.ValidationError(
                        _(
                            "Unable to access Facebook templates, please check user id and access token and make sure "
                            + "the whatsapp_business_management permission is enabled"
                        )
                    )
            return self.cleaned_data

    form_class = Form

    def form_valid(self, form):
        from .type import (
            CONFIG_FB_ACCESS_TOKEN,
            CONFIG_FB_BUSINESS_ID,
            CONFIG_FB_NAMESPACE,
            CONFIG_FB_TEMPLATE_LIST_DOMAIN,
        )

        user = self.request.user
        org = user.get_org()

        data = form.cleaned_data

        config = {
            Channel.CONFIG_BASE_URL: data["base_url"],
            Channel.CONFIG_USERNAME: data["username"],
            Channel.CONFIG_PASSWORD: data["password"],
            Channel.CONFIG_AUTH_TOKEN: data["auth_token"],
            CONFIG_FB_BUSINESS_ID: data["facebook_business_id"],
            CONFIG_FB_ACCESS_TOKEN: data["facebook_access_token"],
            CONFIG_FB_NAMESPACE: data["facebook_namespace"],
            CONFIG_FB_TEMPLATE_LIST_DOMAIN: data["facebook_template_list_domain"],
        }

        self.object = Channel.create(
            org,
            user,
            data["country"],
            self.channel_type,
            name="WhatsApp: %s" % data["number"],
            address=data["number"],
            config=config,
            tps=45,
        )

        return super().form_valid(form)

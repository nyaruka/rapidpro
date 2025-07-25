import logging
from collections import defaultdict
from datetime import timedelta
from typing import Any
from uuid import UUID

import phonenumbers
import requests
import twilio.base.exceptions
import vonage
from smartmin.views import (
    SmartCRUDL,
    SmartFormView,
    SmartModelActionView,
    SmartReadView,
    SmartTemplateView,
    SmartUpdateView,
)
from twilio.base.exceptions import TwilioRestException

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template import Context, Engine, TemplateDoesNotExist
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from temba.contacts.models import URN
from temba.ivr.models import Call
from temba.msgs.models import Msg
from temba.orgs.views.base import BaseDependencyDeleteModal, BaseReadView
from temba.orgs.views.mixins import OrgObjPermsMixin, OrgPermsMixin
from temba.utils import countries
from temba.utils.fields import SelectWidget
from temba.utils.views.mixins import ChartViewMixin, ComponentFormMixin, ContextMenuMixin, ModalFormMixin, SpaMixin

from .models import Channel, ChannelCount, ChannelLog

logger = logging.getLogger(__name__)

ALL_COUNTRIES = countries.choices()


def get_channel_read_url(channel):
    return reverse("channels.channel_read", args=[channel.uuid])


class ChannelTypeMixin(SpaMixin):
    """
    Mixin for views owned by a specific channel type
    """

    channel_type = None

    def __init__(self, channel_type):
        self.channel_type = channel_type

        super().__init__()


class ClaimViewMixin(ChannelTypeMixin, OrgPermsMixin, ComponentFormMixin):
    permission = "channels.channel_claim"
    menu_path = "/settings/channels/new-channel"

    class Form(forms.Form):
        def __init__(self, **kwargs):
            self.request = kwargs.pop("request")
            self.channel_type = kwargs.pop("channel_type")
            super().__init__(**kwargs)

        def clean(self):
            if self.channel_type.unique_addresses:
                assert self.cleaned_data.get("address"), "channel type should specify an address in Form.clean method"

                # don't add the same channel address twice
                existing = Channel.objects.filter(
                    is_active=True,
                    address=self.cleaned_data["address"],
                    schemes__overlap=list(self.channel_type.schemes),
                ).first()
                if existing:
                    if existing.org == self.request.org:
                        raise forms.ValidationError(_("This channel is already connected in this workspace."))
                    raise forms.ValidationError(_("This channel is already connected in another workspace."))

            return super().clean()

    def pre_process(self, request, *args, **kwargs):
        if request.org and Channel.is_limit_reached(request.org):
            return HttpResponseRedirect(reverse("orgs.org_workspace"))

        return super().pre_process(request, *args, **kwargs)

    def get_template_names(self):
        return (
            [self.template_name]
            if self.template_name
            else ["channels/types/%s/claim.html" % self.channel_type.slug, "channels/channel_claim_form.html"]
        )

    def derive_title(self):
        return _("Connect %(channel_type)s") % {"channel_type": self.channel_type.name}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        kwargs["channel_type"] = self.channel_type
        return kwargs

    def get_success_url(self):
        if self.channel_type.config_ui:
            return reverse("channels.channel_configuration", args=[self.object.uuid])
        else:
            return reverse("channels.channel_read", args=[self.object.uuid])


class AuthenticatedExternalClaimView(ClaimViewMixin, SmartFormView):
    form_blurb = _("You can connect your number by entering your credentials here.")
    username_label = _("Username")
    username_help = _("The username provided by the provider to use their API")
    password_label = _("Password")
    password_help = _("The password provided by the provider to use their API")

    def __init__(self, **kwargs):
        self.form_blurb = kwargs.pop("form_blurb", self.form_blurb)
        self.username_label = kwargs.pop("username_label", self.username_label)
        self.username_help = kwargs.pop("username_help", self.username_help)
        self.password_label = kwargs.pop("password_label", self.password_label)
        self.password_help = kwargs.pop("password_help", self.password_help)

        super().__init__(**kwargs)

    class Form(ClaimViewMixin.Form):
        country = forms.ChoiceField(
            choices=ALL_COUNTRIES,
            widget=SelectWidget(attrs={"searchable": True}),
            label=_("Country"),
            help_text=_("The country this phone number is used in"),
        )
        number = forms.CharField(
            max_length=14,
            min_length=1,
            label=_("Number"),
            help_text=_("The phone number or short code you are connecting with country code. ex: +250788123124"),
        )
        username = forms.CharField(
            label=_("Username"), help_text=_("The username provided by the provider to use their API")
        )
        password = forms.CharField(
            label=_("Password"), help_text=_("The password provided by the provider to use their API")
        )

        def clean_number(self):
            number = self.data["number"]

            # number is a shortcode, accept as is
            if len(number) > 0 and len(number) < 7:
                return number

            # otherwise, try to parse into an international format
            if number and number[0] != "+":
                number = "+" + number

            try:
                cleaned = phonenumbers.parse(number, None)
                return phonenumbers.format_number(cleaned, phonenumbers.PhoneNumberFormat.E164)
            except Exception:  # pragma: needs cover
                raise forms.ValidationError(
                    _("Invalid phone number, please include the country code. ex: +250788123123")
                )

    form_class = Form

    def lookup_field_label(self, context, field, default=None):
        if field == "password":
            return self.password_label

        elif field == "username":
            return self.username_label

        return super().lookup_field_label(context, field, default=default)

    def lookup_field_help(self, field, default=None):
        if field == "password":
            return self.password_help

        elif field == "username":
            return self.username_help

        return super().lookup_field_help(field, default=default)

    def get_submitted_country(self, data):
        return data["country"]

    def get_channel_config(self, org, data):
        """
        Subclasses can override this method to add in other channel config variables
        """
        return {}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_blurb"] = self.form_blurb
        return context

    def form_valid(self, form):
        org = self.request.org

        data = form.cleaned_data
        extra_config = self.get_channel_config(org, data)
        self.object = Channel.add_authenticated_external_channel(
            org,
            self.request.user,
            self.get_submitted_country(data),
            data["number"],
            data["username"],
            data["password"],
            self.channel_type,
            data.get("url"),
            extra_config=extra_config,
        )

        return super().form_valid(form)


class AuthenticatedExternalCallbackClaimView(AuthenticatedExternalClaimView):
    def get_channel_config(self, org, data):
        return {Channel.CONFIG_CALLBACK_DOMAIN: org.get_brand_domain()}


class BaseClaimNumberMixin(ClaimViewMixin):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        org = self.request.org

        try:
            context["account_numbers"] = self.get_existing_numbers(org)
        except Exception as e:
            context["account_numbers"] = []
            context["error"] = str(e)

        context["search_url"] = self.get_search_url()
        context["claim_url"] = self.get_claim_url()

        context["search_countries"] = self.get_search_countries()
        context["supported_country_iso_codes"] = self.get_supported_country_iso_codes()

        return context

    def get_search_countries(self):
        search_countries = []

        for country in self.get_search_countries_tuple():
            search_countries.append(dict(key=country[0], label=country[1]))

        return search_countries

    def get_supported_country_iso_codes(self):
        supported_country_iso_codes = []

        for country in self.get_supported_countries_tuple():
            supported_country_iso_codes.append(country[0])

        return supported_country_iso_codes

    def get_search_countries_tuple(self):  # pragma: no cover
        raise NotImplementedError(
            'method "get_search_countries_tuple" should be overridden in %s.%s'
            % (self.crudl.__class__.__name__, self.__class__.__name__)
        )

    def get_supported_countries_tuple(self):  # pragma: no cover
        raise NotImplementedError(
            'method "get_supported_countries_tuple" should be overridden in %s.%s'
            % (self.crudl.__class__.__name__, self.__class__.__name__)
        )

    def get_search_url(self):  # pragma: no cover
        raise NotImplementedError(
            'method "get_search_url" should be overridden in %s.%s'
            % (self.crudl.__class__.__name__, self.__class__.__name__)
        )

    def get_claim_url(self):  # pragma: no cover
        raise NotImplementedError(
            'method "get_claim_url" should be overridden in %s.%s'
            % (self.crudl.__class__.__name__, self.__class__.__name__)
        )

    def get_existing_numbers(self, org):  # pragma: no cover
        raise NotImplementedError(
            'method "get_existing_numbers" should be overridden in %s.%s'
            % (self.crudl.__class__.__name__, self.__class__.__name__)
        )

    def is_valid_country(self, calling_code: int) -> bool:  # pragma: no cover
        raise NotImplementedError(
            'method "is_valid_country" should be overridden in %s.%s'
            % (self.crudl.__class__.__name__, self.__class__.__name__)
        )

    def is_messaging_country(self, country_code: str) -> bool:  # pragma: no cover
        raise NotImplementedError(
            'method "is_messaging_country" should be overridden in %s.%s'
            % (self.crudl.__class__.__name__, self.__class__.__name__)
        )

    def claim_number(self, user, phone_number, country, role):  # pragma: no cover
        raise NotImplementedError(
            'method "claim_number" should be overridden in %s.%s'
            % (self.crudl.__class__.__name__, self.__class__.__name__)
        )

    def remove_api_credentials_from_session(self):
        pass

    def form_valid(self, form, *args, **kwargs):
        # must have an org
        org = self.request.org
        if not org:  # pragma: needs cover
            form._errors["upgrade"] = True
            form._errors["phone_number"] = form.error_class(
                [
                    _(
                        "Sorry, you need to have a workspace to add numbers. "
                        "You can still test things out for free using an Android phone."
                    )
                ]
            )
            return self.form_invalid(form)

        data = form.cleaned_data

        # no number parse for short codes
        if len(data["phone_number"]) > 6:
            phone = phonenumbers.parse(data["phone_number"])
            if not self.is_valid_country(phone.country_code):  # pragma: needs cover
                form._errors["phone_number"] = form.error_class(
                    [
                        _(
                            "Sorry, the number you chose is not supported. "
                            "You can still deploy in any country using your "
                            "own SIM card and an Android phone."
                        )
                    ]
                )
                return self.form_invalid(form)

        error_message = None

        # try to claim the number
        try:
            role = Channel.ROLE_CALL + Channel.ROLE_ANSWER
            if self.is_messaging_country(data["country"]):
                role += Channel.ROLE_SEND + Channel.ROLE_RECEIVE
            self.claim_number(self.request.user, data["phone_number"], data["country"], role)
            self.remove_api_credentials_from_session()

            return HttpResponseRedirect("%s?success" % reverse("public.public_welcome"))

        except (
            vonage.AuthenticationError,
            vonage.ClientError,
            twilio.base.exceptions.TwilioRestException,
        ) as e:  # pragma: no cover
            logger.warning(f"Unable to claim a number: {str(e)}", exc_info=True)
            error_message = form.error_class([str(e)])

        except Exception as e:  # pragma: needs cover
            logger.error(f"Unable to claim a number: {str(e)}", exc_info=True)

            message = str(e)
            if message:
                error_message = form.error_class([message])
            else:
                error_message = form.error_class(
                    [
                        _(
                            "An error occurred connecting your Twilio number, try removing your "
                            "Twilio account, reconnecting it and trying again."
                        )
                    ]
                )

        if error_message is not None:
            form._errors["phone_number"] = error_message

        return self.form_invalid(form)


class UpdateChannelForm(forms.ModelForm):
    name = forms.CharField(
        label=_("Name"), max_length=64, required=True, help_text=_("Descriptive name for this channel.")
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.config_fields = []

        if URN.TEL_SCHEME in self.instance.schemes:
            self.add_config_field(
                Channel.CONFIG_ALLOW_INTERNATIONAL,
                forms.BooleanField(required=False, help_text=_("Allow sending to and calling international numbers.")),
                default=False,
            )

        if Channel.ROLE_CALL in self.instance.role:
            self.add_config_field(
                Channel.CONFIG_MACHINE_DETECTION,
                forms.BooleanField(
                    required=False, help_text=_("Perform answering machine detection and hangup if machine detected.")
                ),
                default=False,
            )

    def add_config_field(self, config_key: str, field, *, default):
        field.initial = self.instance.config.get(config_key, default)

        self.fields[config_key] = field
        self.config_fields.append(config_key)

    def get_config_values(self):
        return {k: v for k, v in self.cleaned_data.items() if k in self.config_fields}

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        updated_config = self.instance.config | self.get_config_values()

        if not Channel.get_type_from_code(self.instance.channel_type).check_credentials(updated_config):
            raise ValidationError(_("Credentials don't appear to be valid."))
        return cleaned_data

    class Meta:
        model = Channel
        fields = ("name", "is_enabled", "log_policy")
        readonly = ()
        labels = {"is_enabled": _("Enabled")}


class ChannelCRUDL(SmartCRUDL):
    model = Channel
    actions = (
        "chart",
        "claim",
        "claim_all",
        "update",
        "read",
        "delete",
        "configuration",
        "logs_list",
        "logs_read",
        "facebook_whitelist",
    )

    class Read(SpaMixin, ContextMenuMixin, BaseReadView):
        slug_url_kwarg = "uuid"
        exclude = ("id", "is_active", "created_by", "modified_by", "modified_on")

        def derive_menu_path(self):
            return f"/settings/channels/{self.object.uuid}"

        def build_context_menu(self, menu):
            obj = self.get_object()

            for item in obj.type.menu_items:
                menu.add_link(item["label"], reverse(item["view_name"], args=[obj.uuid]))

            if obj.type.config_ui:
                menu.add_link(_("Configuration"), reverse("channels.channel_configuration", args=[obj.uuid]))

            menu.add_link(_("Logs"), reverse("channels.channel_logs_list", args=[obj.uuid]))

            if obj.type.template_type:
                menu.add_link(_("Template Logs"), reverse("request_logs.httplog_channel", args=[obj.uuid]))

            if self.has_org_perm("channels.channel_update"):
                menu.add_modax(
                    _("Edit"),
                    "update-channel",
                    reverse("channels.channel_update", args=[obj.id]),
                    title=_("Edit Channel"),
                )
            if self.has_org_perm("channels.channel_delete"):
                menu.add_modax(_("Delete"), "delete-channel", reverse("channels.channel_delete", args=[obj.uuid]))

            if obj.channel_type == "FB" and self.has_org_perm("channels.channel_facebook_whitelist"):
                menu.add_modax(
                    _("Whitelist Domain"),
                    "fb-whitelist",
                    reverse("channels.channel_facebook_whitelist", args=[obj.uuid]),
                )

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            channel = self.object

            context["last_sync"] = channel.last_sync
            context["msg_count"] = channel.get_msg_count()
            context["ivr_count"] = channel.get_ivr_count()

            if channel.is_android:
                context["latest_sync_events"] = channel.sync_events.order_by("-created_on")[:10]

            if not channel.is_new():
                # if the last sync event was more than an hour ago, we have a problem
                if channel.last_sync and (timezone.now() - channel.last_sync.created_on).total_seconds() > 3600:
                    context["delayed_sync_event"] = True

                # unsent messages
                unsent_msgs = channel.get_delayed_outgoing_messages()

                if unsent_msgs:
                    context["unsent_msgs_count"] = unsent_msgs.count()

            context["monthly_counts"] = self.get_monthly_counts()
            return context

        def get_monthly_counts(self) -> list:
            # for every month since this channel was started
            since = self.object.created_on.replace(day=1).date()
            until = timezone.now().date() + timedelta(days=1)

            # get our totals grouped by month+scope
            counts = (
                self.object.counts.period(since, until)
                .filter(
                    scope__in=[
                        ChannelCount.SCOPE_TEXT_IN,
                        ChannelCount.SCOPE_TEXT_OUT,
                        ChannelCount.SCOPE_VOICE_IN,
                        ChannelCount.SCOPE_VOICE_OUT,
                    ]
                )
                .month_totals(scoped=True)
            )

            # covert into a table of totals by month
            by_month = []
            month = since
            while month < until:
                by_month.append(
                    dict(
                        month_start=month,
                        text_in=counts.get((month, ChannelCount.SCOPE_TEXT_IN), 0),
                        text_out=counts.get((month, ChannelCount.SCOPE_TEXT_OUT), 0),
                        voice_in=counts.get((month, ChannelCount.SCOPE_VOICE_IN), 0),
                        voice_out=counts.get((month, ChannelCount.SCOPE_VOICE_OUT), 0),
                    )
                )
                month = (month + timedelta(days=32)).replace(day=1)

            # reverse our table so most recent is first
            by_month.reverse()
            return by_month

    class Chart(ChartViewMixin, BaseReadView):
        permission = "channels.channel_read"
        slug_url_kwarg = "uuid"
        default_chart_period = (-timedelta(days=30), timedelta(days=1))

        def get_chart_data(self, since, until) -> tuple[list, list]:
            counts = (
                self.object.counts.period(since, until)
                .filter(
                    scope__in=[
                        ChannelCount.SCOPE_TEXT_IN,
                        ChannelCount.SCOPE_TEXT_OUT,
                        ChannelCount.SCOPE_VOICE_IN,
                        ChannelCount.SCOPE_VOICE_OUT,
                    ],
                )
                .day_totals(scoped=True)
            )

            # collect all dates and values by scope
            dates_set = set()
            values_by_scope = {
                ChannelCount.SCOPE_TEXT_IN: {},
                ChannelCount.SCOPE_TEXT_OUT: {},
                ChannelCount.SCOPE_VOICE_IN: {},
                ChannelCount.SCOPE_VOICE_OUT: {},
            }

            for (day, scope), count in counts.items():
                dates_set.add(day)
                values_by_scope[scope][day] = count

            # create sorted list of dates
            labels = sorted(list(dates_set))

            ivr_count = self.object.get_ivr_count()

            # create datasets with fixed splits for Msg In, Msg Out, Voice In, Voice Out
            datasets = [
                {
                    "label": _("Incoming") if not ivr_count else _("Incoming Text"),
                    "data": [values_by_scope[ChannelCount.SCOPE_TEXT_IN].get(date, 0) for date in labels],
                },
                {
                    "label": _("Outgoing") if not ivr_count else _("Outgoing Text"),
                    "data": [values_by_scope[ChannelCount.SCOPE_TEXT_OUT].get(date, 0) for date in labels],
                },
            ]

            if ivr_count:
                datasets.extend(
                    [
                        {
                            "label": _("Incoming Voice"),
                            "data": [values_by_scope[ChannelCount.SCOPE_VOICE_IN].get(date, 0) for date in labels],
                        },
                        {
                            "label": _("Outgoing Voice"),
                            "data": [values_by_scope[ChannelCount.SCOPE_VOICE_OUT].get(date, 0) for date in labels],
                        },
                    ]
                )

            return [d.strftime("%Y-%m-%d") for d in labels], datasets

    class FacebookWhitelist(ComponentFormMixin, ModalFormMixin, OrgObjPermsMixin, SmartModelActionView):
        class DomainForm(forms.Form):
            whitelisted_domain = forms.URLField(
                required=True,
                initial="https://",
                help_text="The domain to whitelist for Messenger extensions ex: https://yourdomain.com",
            )

        slug_url_kwarg = "uuid"
        success_url = "uuid@channels.channel_read"
        form_class = DomainForm

        def get_queryset(self):
            return self.request.org.channels.filter(is_active=True, channel_type="FB")

        def execute_action(self):
            # curl -X POST -H "Content-Type: application/json" -d '{
            #  "setting_type" : "domain_whitelisting",
            #  "whitelisted_domains" : ["https://petersfancyapparel.com"],
            #  "domain_action_type": "add"
            # }' "https://graph.facebook.com/v3.3/me/thread_settings?access_token=PAGE_ACCESS_TOKEN"
            access_token = self.object.config[Channel.CONFIG_AUTH_TOKEN]
            response = requests.post(
                "https://graph.facebook.com/v3.3/me/thread_settings?access_token=" + access_token,
                json=dict(
                    setting_type="domain_whitelisting",
                    whitelisted_domains=[self.form.cleaned_data["whitelisted_domain"]],
                    domain_action_type="add",
                ),
            )

            if response.status_code != 200:
                response_json = response.json()
                default_error = dict(message=_("An error occured contacting the Facebook API"))
                raise ValidationError(response_json.get("error", default_error)["message"])

    class Delete(BaseDependencyDeleteModal):
        cancel_url = "uuid@channels.channel_read"
        success_url = "@orgs.org_workspace"
        success_message = _("Your channel has been removed.")
        success_message_twilio = _(
            "We have disconnected your Twilio number. "
            "If you do not need this number you can delete it from the Twilio website."
        )

        def post(self, request, *args, **kwargs):
            channel = self.get_object()

            try:
                channel.release(request.user)
            except TwilioRestException as e:
                messages.error(
                    request,
                    _(f"Twilio reported an error removing your channel (error code {e.code}). Please try again later."),
                )

                response = HttpResponse()
                response["X-Temba-Success"] = self.cancel_url
                return response

            # override success message for Twilio channels
            if channel.channel_type == "T":
                messages.info(request, self.success_message_twilio)
            else:
                messages.info(request, self.success_message)

            response = HttpResponse()
            response["X-Temba-Success"] = self.get_success_url()
            return response

    class Update(ComponentFormMixin, ModalFormMixin, OrgObjPermsMixin, SmartUpdateView):
        field_config = {
            "is_enabled": {
                "help": _("Makes channel available for sending. Incoming messages will be archived if not enabled.")
            }
        }

        def derive_title(self):
            return _("%s Channel") % self.object.type.name

        def derive_exclude(self):
            return [] if self.request.user.is_staff else ["log_policy"]

        def derive_readonly(self):
            return self.form.Meta.readonly if hasattr(self, "form") else []

        def get_success_url(self):
            return reverse("channels.channel_read", args=[self.object.uuid])

        def get_form_class(self):
            return Channel.get_type_from_code(self.object.channel_type).get_update_form()

        def derive_initial(self):
            initial = super().derive_initial()
            initial["role"] = [char for char in self.object.role]
            return initial

        def pre_save(self, obj):
            obj.config.update(self.form.get_config_values())
            return obj

    class Claim(SpaMixin, OrgPermsMixin, SmartTemplateView):
        title = _("New Channel")
        menu_path = "/settings/channels/new-channel"

        def channel_types_groups(self):
            org = self.request.org
            user = self.request.user

            # fetch channel types, sorted by category and name
            types_by_category = defaultdict(list)
            recommended_channels = []
            for ch_type in list(Channel.get_types()):
                region_aware_visible, region_ignore_visible = ch_type.is_available_to(org, user)

                if ch_type.is_recommended_to(org, user):
                    recommended_channels.append(ch_type)
                elif region_ignore_visible and region_aware_visible and ch_type.category:
                    types_by_category[ch_type.category.name].append(ch_type)

            return recommended_channels, types_by_category, True

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            org = self.request.org

            context["org_timezone"] = str(org.timezone)
            context["limit_reached"] = Channel.is_limit_reached(org)

            # fetch channel types, sorted by category and name
            recommended_channels, types_by_category, only_regional_channels = self.channel_types_groups()

            context["recommended_channels"] = recommended_channels
            context["channel_types"] = types_by_category
            context["only_regional_channels"] = only_regional_channels
            return context

    class ClaimAll(Claim):
        def channel_types_groups(self):
            org = self.request.org
            user = self.request.user

            types_by_category = defaultdict(list)
            recommended_channels = []
            for ch_type in list(Channel.get_types()):
                _, region_ignore_visible = ch_type.is_available_to(org, user)
                if ch_type.is_recommended_to(org, user):
                    recommended_channels.append(ch_type)
                elif region_ignore_visible and ch_type.category:
                    types_by_category[ch_type.category.name].append(ch_type)

            return recommended_channels, types_by_category, False

    class Configuration(SpaMixin, BaseReadView):
        slug_url_kwarg = "uuid"

        def pre_process(self, request, *args, **kwargs):
            channel = self.get_object()
            if not channel.type.config_ui:
                return HttpResponseRedirect(reverse("channels.channel_read", args=[channel.uuid]))

            return super().pre_process(request, *args, **kwargs)

        def derive_menu_path(self):
            return f"/settings/channels/{self.object.uuid}"

        def get_blurb_from_template(self, channel) -> str:
            try:
                return (
                    Engine.get_default()
                    .get_template("channels/types/%s/config.html" % channel.type.slug)
                    .render(context=Context(channel.type.get_config_ui_context(channel)))
                )
            except TemplateDoesNotExist:
                return None

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)

            endpoints = []
            for endpoint in self.object.type.config_ui.get_used_endpoints(self.object):
                endpoints.append(dict(url=endpoint.get_url(self.object), label=endpoint.label, help=endpoint.help))

            if self.object.type.config_ui.show_secret:
                secret = self.object.secret or self.object.config.get("secret")
            else:
                secret = None

            context["blurb"] = self.get_blurb_from_template(self.object) or self.object.type.config_ui.blurb
            context["endpoints"] = endpoints
            context["secret"] = secret
            context["ip_addresses"] = settings.IP_ADDRESSES if self.object.type.config_ui.show_public_ips else None

            return context

    class LogsList(SpaMixin, OrgObjPermsMixin, SmartReadView):
        permission = "channels.channel_logs"
        slug_url_kwarg = "uuid"
        paginate_by = 50
        title = _("Channel Logs")

        @classmethod
        def derive_url_pattern(cls, path, action):
            return r"^%s/logs/(?P<uuid>[0-9a-f-]{36})/$" % path

        def derive_menu_path(self):
            return f"/settings/channels/{self.kwargs['uuid']}"

        def get_context_data(self, **kwargs):
            this_after = self.request.GET.get("after")
            if this_after:
                this_after = UUID(this_after)

            logs, prev_after, next_after = ChannelLog.get_by_channel(
                self.object, limit=self.paginate_by, after_uuid=this_after
            )

            context = super().get_context_data(**kwargs)
            context["logs"] = logs
            context["page_obj"] = {
                "previous_page_after": prev_after,
                "next_page_after": next_after,
                "has_previous": bool(this_after),
                "has_next": bool(next_after),
            }
            return context

    class LogsRead(SpaMixin, OrgObjPermsMixin, SmartReadView):
        permission = "channels.channel_logs"
        slug_url_kwarg = "uuid"
        title = _("Channel Log")

        @classmethod
        def derive_url_pattern(cls, path, action):
            return r"^%s/logs/(?P<uuid>[0-9a-f-]{36})/(?P<reftype>log|msg|call)/(?P<refid>[^/]{1,36})/$" % path

        def derive_menu_path(self):
            return f"/settings/channels/{self.kwargs['uuid']}"

        @cached_property
        def owner(self) -> Msg | Call | None:
            if self.kwargs["reftype"] == "msg":
                return get_object_or_404(Msg, id=int(self.kwargs["refid"]), org=self.request.org)
            elif self.kwargs["reftype"] == "call":
                return get_object_or_404(Call, id=int(self.kwargs["refid"]), org=self.request.org)
            return None

        def get_logs_and_urn(self) -> tuple:
            if self.owner:
                return self.owner.get_logs(), self.owner.contact_urn

            return ChannelLog.get_by_uuid(self.object, [UUID(self.kwargs["refid"])]), None

        def get_context_data(self, **kwargs):
            anonymize = self.request.org.is_anon and not (self.request.GET.get("break") and self.request.user.is_staff)
            raw_logs, owner_urn = self.get_logs_and_urn()

            logs = []
            for log in raw_logs:
                logs.append(log.get_display(anonymize=anonymize, urn=owner_urn))

            context = super().get_context_data(**kwargs)
            context["msg"] = self.owner if isinstance(self.owner, Msg) else None
            context["call"] = self.owner if isinstance(self.owner, Call) else None
            context["logs"] = logs
            return context

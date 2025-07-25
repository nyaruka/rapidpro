import logging
from abc import ABCMeta
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

import iso8601
import phonenumbers
import requests
from django_countries.fields import CountryField
from django_valkey import get_valkey_connection
from phonenumbers import NumberParseException
from twilio.base.exceptions import TwilioRestException

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import OpClass
from django.db import models
from django.db.models import Q
from django.template import Engine
from django.urls import re_path
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from temba import mailroom
from temba.orgs.models import DependencyMixin, Org
from temba.utils import dynamo, on_transaction_commit, redact
from temba.utils.models import (
    JSONAsTextField,
    LegacyUUIDMixin,
    TembaModel,
    TembaUUIDMixin,
    delete_in_batches,
    generate_uuid,
)
from temba.utils.models.counts import BaseDailyCount
from temba.utils.text import generate_secret
from temba.utils.whatsapp import update_api_version

logger = logging.getLogger(__name__)


@dataclass
class ConfigUI:
    """
    Parameterized configuration view for a channel type.
    """

    @dataclass
    class Endpoint:
        """
        Courier (messages) or mailroom (IVR) endpoint that the user needs to configure on the other side.
        """

        label: str
        help: str = ""
        courier: str = None
        mailroom: str = None
        roles: tuple[str] = ()

        def get_url(self, channel) -> str:
            if self.courier is not None:
                path = f"/c/{channel.type.code.lower()}/{channel.uuid}/{self.courier}"
            elif self.mailroom is not None:
                path = f"/mr/ivr/c/{channel.uuid}/{self.mailroom}"

            return f"https://{channel.callback_domain}{path}"

    blurb: str = None
    endpoints: tuple[Endpoint] = ()
    show_secret: bool = False
    show_public_ips: bool = False

    def get_used_endpoints(self, channel) -> list:
        """
        Gets the endpoints used by the given channel based on its roles.
        """
        return [e for e in self.endpoints if not e.roles or set(channel.role) & set(e.roles)]


class ChannelType(metaclass=ABCMeta):
    """
    Base class for all dynamic channel types
    """

    class Category(Enum):
        PHONE = 1
        SOCIAL_MEDIA = 2
        API = 4

    code = None  # DB code and lowercased to create courier URLs
    slug = None  # set automatically
    name = None  # display name
    category = None
    beta_only = False

    unique_addresses = False

    # the courier handling URL, will be wired automatically for use in templates, but wired to a null handler
    courier_url = None

    schemes = None
    available_timezones = None
    recommended_timezones = None

    claim_blurb = None
    claim_view = None
    claim_view_kwargs = None

    # the configuration UI - only channel types that aren't configured automatically need this
    config_ui = None

    update_form = None

    # additional read page content menu items
    menu_items = ()

    # Whether this channel should be activated in the a celery task, useful to turn off if there's a chance for errors
    # during activation. Channels should make sure their claim view is non-atomic if a callback will be involved
    async_activation = True

    # used for anonymizing logs
    redact_request_keys = ()
    redact_response_keys = ()

    # for channels that support templates this is the type slug and the channel type must define fetch_templates
    template_type: str = None

    def is_available_to(self, org, user):
        """
        Determines whether this channel type is available to the given user considering the region and when not considering region, e.g. check timezone
        """
        region_ignore_visible = (not self.beta_only) or user.is_beta
        region_aware_visible = True

        if self.available_timezones is not None:
            region_aware_visible = org.timezone and str(org.timezone) in self.available_timezones

        return region_aware_visible, region_ignore_visible

    def is_recommended_to(self, org, user):
        """
        Determines whether this channel type is recommended to the given user.
        """
        if self.recommended_timezones is not None:
            return org.timezone and str(org.timezone) in self.recommended_timezones
        else:
            return False

    @property
    def icon(self):
        return f"channel_{self.code.lower()}"

    def get_claim_blurb(self):
        """
        Gets the blurb for use on the claim page list of channel types
        """
        return Engine.get_default().from_string(self.claim_blurb)

    def get_urls(self):
        """
        Returns all the URLs this channel exposes to Django, the URL should be relative.
        """
        return [self.get_claim_url()]

    def get_claim_url(self):
        """
        Gets the URL/view configuration for this channel types's claim page
        """
        claim_view_kwargs = self.claim_view_kwargs if self.claim_view_kwargs else {}
        claim_view_kwargs["channel_type"] = self
        return re_path(r"^claim/$", self.claim_view.as_view(**claim_view_kwargs), name="claim")

    def get_update_form(self):
        if self.update_form is None:
            from .views import UpdateChannelForm

            return UpdateChannelForm
        return self.update_form

    def check_credentials(self, config: dict) -> bool:
        """
        Called to check the credentials passed are valid
        """
        return True

    def activate(self, channel):
        """
        Called when a channel of this type has been created. Can be used to setup things like callbacks required by the
        channel.
        """

    def deactivate(self, channel):
        """
        Called when a channel of this type has been released. Can be used to cleanup things like callbacks which were
        used by the channel.
        """

    def activate_trigger(self, trigger):
        """
        Called when a trigger that is bound to a channel of this type is being created or restored.
        """

    def deactivate_trigger(self, trigger):
        """
        Called when a trigger that is bound to a channel of this type is being released.
        """

    def get_config_ui_context(self, channel) -> dict:
        """
        Context for the config UI if a custom template is provided
        """
        return {"channel": channel}

    def get_redact_values(self, channel) -> tuple:
        """
        Gets the values to redact from logs
        """
        return ()

    def get_error_ref_url(self, channel, code: str) -> str:
        """
        Resolves an error code from a channel log into a docs URL for that error.
        """

    def __str__(self):
        return self.name


def _get_default_channel_scheme():
    return ["tel"]


class Channel(LegacyUUIDMixin, TembaModel, DependencyMixin):
    """
    Notes:
        - we want to reuse keys as much as possible (2018-10-11)
        - prefixed keys are legacy and should be avoided (2018-10-11)
    """

    # keys for various config options stored in the channel config dict
    CONFIG_BASE_URL = "base_url"
    CONFIG_SEND_URL = "send_url"

    CONFIG_USERNAME = "username"
    CONFIG_PASSWORD = "password"
    CONFIG_KEY = "key"
    CONFIG_API_ID = "api_id"
    CONFIG_API_KEY = "api_key"
    CONFIG_VERIFY_SSL = "verify_ssl"
    CONFIG_USE_NATIONAL = "use_national"
    CONFIG_ENCODING = "encoding"
    CONFIG_PAGE_NAME = "page_name"

    CONFIG_AUTH_TOKEN = "auth_token"
    CONFIG_SECRET = "secret"
    CONFIG_CHANNEL_ID = "channel_id"
    CONFIG_CHANNEL_MID = "channel_mid"
    CONFIG_FCM_ID = "FCM_ID"
    CONFIG_RP_HOSTNAME_OVERRIDE = "rp_hostname_override"
    CONFIG_CALLBACK_DOMAIN = "callback_domain"
    CONFIG_ACCOUNT_SID = "account_sid"
    CONFIG_APPLICATION_SID = "application_sid"
    CONFIG_NUMBER_SID = "number_sid"

    CONFIG_MAX_CONCURRENT_CALLS = "max_concurrent_calls"
    CONFIG_ALLOW_INTERNATIONAL = "allow_international"
    CONFIG_MACHINE_DETECTION = "machine_detection"

    ENCODING_DEFAULT = "D"  # we just pass the text down to the endpoint
    ENCODING_SMART = "S"  # we try simple substitutions to GSM7 then go to unicode if it still isn't GSM7
    ENCODING_UNICODE = "U"  # we send everything as unicode
    ENCODING_CHOICES = (
        (ENCODING_DEFAULT, _("Default Encoding")),
        (ENCODING_SMART, _("Smart Encoding")),
        (ENCODING_UNICODE, _("Unicode Encoding")),
    )

    # the role types for our channels
    ROLE_SEND = "S"
    ROLE_RECEIVE = "R"
    ROLE_CALL = "C"
    ROLE_ANSWER = "A"
    ROLE_USSD = "U"
    DEFAULT_ROLE = ROLE_SEND + ROLE_RECEIVE

    CONTENT_TYPE_URLENCODED = "urlencoded"
    CONTENT_TYPE_JSON = "json"
    CONTENT_TYPE_XML = "xml"
    CONTENT_TYPES = {
        CONTENT_TYPE_URLENCODED: "application/x-www-form-urlencoded",
        CONTENT_TYPE_JSON: "application/json",
        CONTENT_TYPE_XML: "text/xml; charset=utf-8",
    }
    CONTENT_TYPE_CHOICES = (
        (CONTENT_TYPE_URLENCODED, _("URL Encoded - application/x-www-form-urlencoded")),
        (CONTENT_TYPE_JSON, _("JSON - application/json")),
        (CONTENT_TYPE_XML, _("XML - text/xml; charset=utf-8")),
    )

    LOG_POLICY_NONE = "N"
    LOG_POLICY_ERRORS = "E"
    LOG_POLICY_ALL = "A"
    LOG_POLICY_CHOICES = (
        (LOG_POLICY_NONE, "Discard All"),
        (LOG_POLICY_ERRORS, "Write Errors Only"),
        (LOG_POLICY_ALL, "Write All"),
    )

    SIMULATOR_CHANNEL = {
        "uuid": "440099cf-200c-4d45-a8e7-4a564f4a0e8b",
        "name": "Simulator Channel",
        "address": "+18005551212",
        "schemes": ["tel"],
        "roles": ["send"],
    }

    org_limit_key = Org.LIMIT_CHANNELS

    org = models.ForeignKey(Org, on_delete=models.PROTECT, related_name="channels", null=True)
    channel_type = models.CharField(max_length=3)
    name = models.CharField(max_length=64)
    address = models.CharField(
        verbose_name=_("Address"),
        max_length=255,
        blank=True,
        null=True,
        help_text=_("Address with which this channel communicates"),
    )

    country = CountryField(
        verbose_name=_("Country"), null=True, blank=True, help_text=_("Country which this channel is for")
    )

    config = models.JSONField(default=dict)
    schemes = ArrayField(models.CharField(max_length=16), default=_get_default_channel_scheme)
    role = models.CharField(max_length=4, default=DEFAULT_ROLE)
    log_policy = models.CharField(max_length=1, default=LOG_POLICY_ALL, choices=LOG_POLICY_CHOICES)
    tps = models.IntegerField(null=True)
    is_enabled = models.BooleanField(default=True)

    # Android relayer specific fields
    claim_code = models.CharField(max_length=16, blank=True, null=True, unique=True)
    secret = models.CharField(max_length=64, blank=True, null=True, unique=True)
    device = models.CharField(max_length=255, null=True, blank=True)
    os = models.CharField(max_length=255, null=True, blank=True)
    last_seen = models.DateTimeField(null=True)

    @classmethod
    def create(
        cls,
        org,
        user,
        country,
        channel_type,
        name=None,
        address=None,
        config=None,
        role=DEFAULT_ROLE,
        schemes=None,
        normalize_urns=True,
        **kwargs,
    ):
        if isinstance(channel_type, str):
            channel_type = cls.get_type_from_code(channel_type)

        if schemes:
            if channel_type.schemes and not set(channel_type.schemes).intersection(schemes):
                raise ValueError("Channel type '%s' cannot support schemes %s" % (channel_type, schemes))
        else:
            schemes = channel_type.schemes

        if not schemes:
            raise ValueError("Cannot create channel without schemes")

        if country and schemes[0] not in ["tel", "whatsapp"]:
            raise ValueError("Only channels handling phone numbers can be country specific")

        if config is None:
            config = {}

        create_args = dict(
            org=org,
            country=country,
            channel_type=channel_type.code,
            name=name or address,
            address=address,
            config=config,
            role=role,
            schemes=schemes,
            created_by=user,
            modified_by=user,
        )
        create_args.update(kwargs)

        if "uuid" not in create_args:
            create_args["uuid"] = generate_uuid()

        channel = cls.objects.create(**create_args)

        # normalize any telephone numbers that we may now have a clue as to country
        if org and country and "tel" in schemes and normalize_urns:
            org.normalize_contact_tels()

        if channel_type.async_activation:
            on_transaction_commit(lambda: channel_type.activate(channel))
        else:
            try:
                channel_type.activate(channel)

            except Exception as e:
                # release our channel, raise error upwards
                channel.release(user, interrupt=False)
                raise e

        return channel

    @classmethod
    def get_type_from_code(cls, code):
        from .types import TYPES

        try:
            return TYPES[code]
        except KeyError:  # pragma: no cover
            raise ValueError("Unrecognized channel type code: %s" % code)

    @classmethod
    def get_types(cls):
        from .types import TYPES

        return TYPES.values()

    @property
    def type(self) -> ChannelType:
        return self.get_type_from_code(self.channel_type)

    @property
    def template_type(self):
        from temba.templates.types import TYPES

        return TYPES.get(self.type.template_type)

    def refresh_templates(self):
        from temba.notifications.incidents.builtin import ChannelTemplatesFailedIncidentType
        from temba.request_logs.models import HTTPLog
        from temba.templates.models import TemplateTranslation

        r = get_valkey_connection()

        key = "refresh_channel_templates_%d" % self.id

        # we need to make sure the channel is not syncing the templates
        if r.get(key):  # pragma: no cover
            return

        with r.lock(key, 60):
            # for channels which have version in their config, refresh it
            if self.config.get("version"):
                update_api_version(self)

            try:
                raw_templates = self.type.fetch_templates(self)

                TemplateTranslation.update_local(self, raw_templates)

                # if we have an ongoing template incident, end it
                ongoing = self.incidents.filter(
                    incident_type=ChannelTemplatesFailedIncidentType.slug, ended_on=None
                ).first()
                if ongoing:
                    ongoing.end()
            except requests.RequestException as e:
                # if last 5 sync attempts have been errors, create an incident
                recent_is_errors = list(
                    self.http_logs.filter(log_type=HTTPLog.WHATSAPP_TEMPLATES_SYNCED)
                    .order_by("-id")
                    .values_list("is_error", flat=True)[:5]
                )
                if len(recent_is_errors) >= 5 and all(recent_is_errors):
                    ChannelTemplatesFailedIncidentType.get_or_create(self)
                raise e

    @classmethod
    def add_authenticated_external_channel(
        cls,
        org,
        user,
        country,
        phone_number,
        username,
        password,
        channel_type,
        url,
        role=DEFAULT_ROLE,
        extra_config=None,
    ):
        try:
            parsed = phonenumbers.parse(phone_number, None)
            phone = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        except Exception:
            # this is a shortcode, just use it plain
            phone = phone_number

        config = dict(username=username, password=password, send_url=url)
        if extra_config:
            config.update(extra_config)

        return Channel.create(
            org, user, country, channel_type, name=phone, address=phone_number, config=config, role=role
        )

    @classmethod
    def add_config_external_channel(
        cls,
        org,
        user,
        country,
        address,
        channel_type,
        config,
        role=DEFAULT_ROLE,
        schemes=("tel",),
        name=None,
        tps=None,
    ):
        return Channel.create(
            org,
            user,
            country,
            channel_type,
            name=name or address[:64],
            address=address,
            config=config,
            role=role,
            schemes=schemes,
            tps=tps,
        )

    @classmethod
    def generate_secret(cls, length=64):
        """
        Generates a secret value used for command signing
        """
        code = generate_secret(length)
        while cls.objects.filter(secret=code):  # pragma: no cover
            code = generate_secret(length)
        return code

    @property
    def is_android(self) -> bool:
        """
        Is this an Android channel
        """
        from .types.android.type import AndroidType

        return self.channel_type == AndroidType.code

    @property
    def callback_domain(self):
        """
        Returns the domain to use for callbacks, this can be channel specific if set on the config, otherwise the brand domain
        """
        callback_domain = self.config.get(Channel.CONFIG_CALLBACK_DOMAIN)

        if callback_domain:
            return callback_domain
        else:
            return self.org.get_brand_domain()

    def supports_ivr(self):
        return Channel.ROLE_CALL in self.role or Channel.ROLE_ANSWER in self.role

    def get_address_display(self, e164=False):
        from temba.contacts.models import URN

        if not self.address:
            return ""

        if self.address and URN.TEL_SCHEME in self.schemes and self.country:
            # assume that a number not starting with + is a short code and return as is
            if self.address[0] != "+":
                return self.address

            try:
                normalized = phonenumbers.parse(self.address, str(self.country))
                fmt = phonenumbers.PhoneNumberFormat.E164 if e164 else phonenumbers.PhoneNumberFormat.INTERNATIONAL
                return phonenumbers.format_number(normalized, fmt)
            except NumberParseException:  # pragma: needs cover
                # the number may be alphanumeric in the case of short codes
                pass

        elif URN.FACEBOOK_SCHEME in self.schemes:
            return "%s (%s)" % (self.config.get(Channel.CONFIG_PAGE_NAME, self.name), self.address)

        elif self.channel_type == "WAC":
            return "%s (%s)" % (self.config.get("wa_number", ""), self.config.get("wa_verified_name", self.name))

        return self.address

    def get_last_sent_message(self):
        from temba.msgs.models import Msg

        # find last successfully sent message
        return (
            self.msgs.filter(status__in=[Msg.STATUS_SENT, Msg.STATUS_DELIVERED], direction=Msg.DIRECTION_OUT)
            .exclude(sent_on=None)
            .order_by("-sent_on")
            .first()
        )

    def get_delayed_outgoing_messages(self):
        from temba.msgs.models import Msg

        one_hour_ago = timezone.now() - timedelta(hours=1)
        latest_sent_message = self.get_last_sent_message()

        # if the last sent message was in the last hour, assume this channel is ok
        if latest_sent_message and latest_sent_message.sent_on > one_hour_ago:  # pragma: no cover
            return Msg.objects.none()

        messages = self.get_unsent_messages()

        # channels have an hour to send messages before we call them delays, so ignore all messages created in last hour
        messages = messages.filter(created_on__lt=one_hour_ago)

        # if we have a successfully sent message, we're only interested a new failures since then. Note that we use id
        # here instead of created_on because we won't hit the outbox index if we use a range condition on created_on.
        if latest_sent_message:  # pragma: needs cover
            messages = messages.filter(id__gt=latest_sent_message.id)

        return messages

    @cached_property
    def last_sync(self):
        """
        Gets the last sync event for this channel (only applies to Android channels)
        """
        return self.sync_events.order_by("id").last()

    def get_unsent_messages(self):
        # use our optimized index for our org outbox
        from temba.msgs.models import Msg

        return Msg.objects.filter(org=self.org.id, status__in=["P", "Q"], direction="O", visibility="V", channel=self)

    def is_new(self):
        # is this channel newer than an hour
        return self.created_on > timezone.now() - timedelta(hours=1) or not self.last_sync

    def check_credentials(self) -> bool:
        return self.type.check_credentials(self.config)

    def release(self, user, *, trigger_sync: bool = True, interrupt: bool = True):
        """
        Releases this channel making it inactive
        """
        from temba.channels.tasks import interrupt_channel_task

        super().release(user)

        # ask the channel type to deactivate - as this usually means calling out to external APIs it can fail
        try:
            self.type.deactivate(self)
        except TwilioRestException as e:
            raise e
        except Exception as e:
            # proceed with removing this channel but log the problem
            logger.error(f"Unable to deactivate a channel: {str(e)}", exc_info=True)

        # make the channel inactive
        self.modified_by = user
        self.is_active = False
        self.save(update_fields=("is_active", "modified_by", "modified_on"))

        if interrupt:
            # delay mailroom call for 5 seconds, so mailroom assets cache expires
            interrupt_channel_task.apply_async((self.id,), countdown=5)

        # trigger the orphaned channel
        if trigger_sync and self.is_android:
            mailroom.get_client().android_sync(self)

        # any triggers associated with our channel get archived and released
        for trigger in self.triggers.filter(is_active=True):
            try:
                trigger.archive(user)
            except Exception as e:
                logger.error(f"Unable to deactivate a channel trigger: {str(e)}", exc_info=True)

            trigger.release(user)

        # any open incidents are ended
        for incident in self.incidents.filter(ended_on=None):
            incident.end()

        # delete template translations for this channel
        for trans in self.template_translations.all():
            trans.delete()

    def delete(self):
        for trigger in self.triggers.all():
            trigger.delete()

        delete_in_batches(self.incidents.all())
        delete_in_batches(self.sync_events.all())
        delete_in_batches(self.http_logs.all())
        delete_in_batches(self.template_translations.all())
        delete_in_batches(self.counts.all())

        super().delete()

    def get_msg_count(self, since=None):
        counts = self.counts.filter(scope__in=[ChannelCount.SCOPE_TEXT_IN, ChannelCount.SCOPE_TEXT_OUT])
        if since:
            counts = counts.filter(day__gte=since)

        return counts.sum()

    def get_ivr_count(self):
        return self.counts.filter(scope__in=[ChannelCount.SCOPE_VOICE_IN, ChannelCount.SCOPE_VOICE_OUT]).sum()

    class Meta:
        ordering = ("-last_seen", "-pk")

        indexes = [
            models.Index(
                name="channels_android_last_seen",
                fields=("last_seen",),
                condition=Q(channel_type="A", is_active=True, last_seen__isnull=False),
            ),
        ]


class ChannelCount(BaseDailyCount):
    """
    Tracks counts of messages in/out every day.
    """

    squash_over = ("channel_id", "day", "scope")

    SCOPE_TEXT_IN = "text:in"
    SCOPE_TEXT_OUT = "text:out"
    SCOPE_VOICE_IN = "voice:in"
    SCOPE_VOICE_OUT = "voice:out"

    channel = models.ForeignKey(Channel, on_delete=models.PROTECT, related_name="counts", db_index=False)

    class Meta:
        indexes = [
            models.Index(
                "channel", "day", OpClass("scope", name="varchar_pattern_ops"), name="channelcount_channel_scope"
            ),
            # for squashing task
            models.Index(
                name="channelcount_unsquashed", fields=("channel", "day", "scope"), condition=Q(is_squashed=False)
            ),
        ]


class ChannelEvent(TembaUUIDMixin, models.Model):
    """
    An event other than a message that occurs between a channel and a contact. Can be used to trigger flows etc.
    """

    TYPE_CALL_OUT = "mt_call"
    TYPE_CALL_OUT_MISSED = "mt_miss"
    TYPE_CALL_IN = "mo_call"
    TYPE_CALL_IN_MISSED = "mo_miss"
    TYPE_NEW_CONVERSATION = "new_conversation"
    TYPE_REFERRAL = "referral"
    TYPE_STOP_CONTACT = "stop_contact"
    TYPE_WELCOME_MESSAGE = "welcome_message"
    TYPE_OPTIN = "optin"
    TYPE_OPTOUT = "optout"
    TYPE_DELETE_CONTACT = "delete_contact"

    # single char flag, human readable name, API readable name
    TYPE_CONFIG = (
        (TYPE_CALL_OUT, _("Outgoing Call"), "call-out"),
        (TYPE_CALL_OUT_MISSED, _("Missed Outgoing Call"), "call-out-missed"),
        (TYPE_CALL_IN, _("Incoming Call"), "call-in"),
        (TYPE_CALL_IN_MISSED, _("Missed Incoming Call"), "call-in-missed"),
        (TYPE_STOP_CONTACT, _("Stop Contact"), "stop-contact"),
        (TYPE_NEW_CONVERSATION, _("New Conversation"), "new-conversation"),
        (TYPE_REFERRAL, _("Referral"), "referral"),
        (TYPE_WELCOME_MESSAGE, _("Welcome Message"), "welcome-message"),
        (TYPE_OPTIN, _("Opt In"), "optin"),
        (TYPE_OPTOUT, _("Opt Out"), "optout"),
        (TYPE_DELETE_CONTACT, _("Delete Contact"), "delete-contact"),
    )

    TYPE_CHOICES = [(t[0], t[1]) for t in TYPE_CONFIG]

    ALL_TYPES = {t[0] for t in TYPE_CONFIG}
    CALL_TYPES = {TYPE_CALL_OUT, TYPE_CALL_OUT_MISSED, TYPE_CALL_IN, TYPE_CALL_IN_MISSED}

    STATUS_PENDING = "P"
    STATUS_HANDLED = "H"
    STATUS_CHOICES = ((STATUS_PENDING, "Pending"), (STATUS_HANDLED, "Handled"))

    org = models.ForeignKey(Org, on_delete=models.PROTECT)
    channel = models.ForeignKey(Channel, on_delete=models.PROTECT)
    event_type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, null=True)
    contact = models.ForeignKey("contacts.Contact", on_delete=models.PROTECT, related_name="channel_events")
    contact_urn = models.ForeignKey(
        "contacts.ContactURN", on_delete=models.PROTECT, null=True, related_name="channel_events"
    )
    optin = models.ForeignKey("msgs.OptIn", null=True, on_delete=models.PROTECT, related_name="optins")
    extra = JSONAsTextField(null=True, default=dict)
    occurred_on = models.DateTimeField()
    created_on = models.DateTimeField(default=timezone.now)

    log_uuids = ArrayField(models.UUIDField(), null=True)

    @classmethod
    def is_valid_type(cls, event_type: str) -> bool:
        return event_type in cls.ALL_TYPES


@dataclass
class ChannelLog:
    """
    A log of an interaction with a channel
    """

    DYNAMO_TABLE = "Main"  # unprefixed table name
    REDACT_MASK = "*" * 8  # used to mask redacted values

    LOG_TYPE_UNKNOWN = "unknown"
    LOG_TYPE_MSG_SEND = "msg_send"
    LOG_TYPE_MSG_STATUS = "msg_status"
    LOG_TYPE_MSG_RECEIVE = "msg_receive"
    LOG_TYPE_EVENT_RECEIVE = "event_receive"
    LOG_TYPE_MULTI_RECEIVE = "multi_receive"
    LOG_TYPE_IVR_START = "ivr_start"
    LOG_TYPE_IVR_INCOMING = "ivr_incoming"
    LOG_TYPE_IVR_CALLBACK = "ivr_callback"
    LOG_TYPE_IVR_STATUS = "ivr_status"
    LOG_TYPE_IVR_HANGUP = "ivr_hangup"
    LOG_TYPE_ATTACHMENT_FETCH = "attachment_fetch"
    LOG_TYPE_TOKEN_REFRESH = "token_refresh"
    LOG_TYPE_PAGE_SUBSCRIBE = "page_subscribe"
    LOG_TYPE_WEBHOOK_VERIFY = "webhook_verify"
    LOG_TYPE_DISPLAY = {
        LOG_TYPE_UNKNOWN: _("Other Event"),
        LOG_TYPE_MSG_SEND: _("Message Send"),
        LOG_TYPE_MSG_STATUS: _("Message Status"),
        LOG_TYPE_MSG_RECEIVE: _("Message Receive"),
        LOG_TYPE_EVENT_RECEIVE: _("Event Receive"),
        LOG_TYPE_MULTI_RECEIVE: _("Events Receive"),
        LOG_TYPE_IVR_START: _("IVR Start"),
        LOG_TYPE_IVR_INCOMING: _("IVR Incoming"),
        LOG_TYPE_IVR_CALLBACK: _("IVR Callback"),
        LOG_TYPE_IVR_STATUS: _("IVR Status"),
        LOG_TYPE_IVR_HANGUP: _("IVR Hangup"),
        LOG_TYPE_ATTACHMENT_FETCH: _("Attachment Fetch"),
        LOG_TYPE_TOKEN_REFRESH: _("Token Refresh"),
        LOG_TYPE_PAGE_SUBSCRIBE: _("Page Subscribe"),
        LOG_TYPE_WEBHOOK_VERIFY: _("Webhook Verify"),
    }

    uuid: str
    channel: Channel
    log_type: str
    http_logs: list[dict]
    errors: list[dict]
    is_error: bool
    elapsed_ms: int
    created_on: datetime

    @classmethod
    def get_by_uuid(cls, channel, uuids: list) -> list:
        """
        Get logs from DynamoDB and converts them to non-persistent instances of this class
        """
        if not uuids:
            return []

        keys = [cls._get_key(channel, uuid) for uuid in uuids]
        logs = []

        for item in dynamo.batch_get(dynamo.MAIN, keys):
            if item["OrgID"] == channel.org_id:
                logs.append(cls._from_item(channel, item))

        return sorted(logs, key=lambda l: l.uuid)

    @classmethod
    def get_by_channel(cls, channel, limit=50, after_uuid=None) -> tuple[list, str, str]:
        """
        Gets latest channel logs for given channel. Returns page of logs and the resume UUID to fetch the next page.
        """

        pks = [f"cha#{channel.uuid}#{b}" for b in "0123456789abcdef"]  # each channel has 16 partitions
        after_sk = f"log#{after_uuid}" if after_uuid else None
        items, prev_after_sk, next_after_sk = dynamo.merged_page_query(
            dynamo.MAIN, pks, desc=True, limit=limit, after_sk=after_sk
        )

        prev_after_uuid = prev_after_sk.split("#")[-1] if prev_after_sk else None
        next_after_uuid = next_after_sk.split("#")[-1] if next_after_sk else None

        return [cls._from_item(channel, item) for item in items], prev_after_uuid, next_after_uuid

    @staticmethod
    def _get_key(channel, uuid: str) -> tuple[str, str]:
        return f"cha#{channel.uuid}#{str(uuid)[-1]}", f"log#{uuid}"

    @classmethod
    def _from_item(cls, channel, item: dict):
        assert item["OrgID"] == channel.org_id, "org ID mismatch for channel log"

        data = item["Data"] | dynamo.load_jsongz(item["DataGZ"])

        return cls(
            uuid=item["SK"].split("#")[1],
            channel=channel,
            log_type=data["type"],
            http_logs=data["http_logs"],
            errors=data["errors"],
            is_error=data.get("is_error", False),
            elapsed_ms=int(data["elapsed_ms"]),
            created_on=iso8601.parse_date(data["created_on"]),
        )

    def get_log_type_display(self) -> str:
        return self.LOG_TYPE_DISPLAY.get(self.log_type, self.log_type)

    def get_display(self, *, anonymize: bool, urn) -> dict:
        """
        Gets a dict representation of this log for display that is optionally anonymized
        """

        # add reference URLs to errors
        errors = [e.copy() for e in self.errors or []]
        for err in errors:
            ext_code = err.get("ext_code")
            err["ref_url"] = self.channel.type.get_error_ref_url(self.channel, ext_code) if ext_code else None

        data = {
            "uuid": str(self.uuid),
            "type": self.log_type,
            "http_logs": [h.copy() for h in self.http_logs or []],
            "errors": errors,
            "is_error": self.is_error,
            "elapsed_ms": self.elapsed_ms,
            "created_on": self.created_on.isoformat(),
        }

        if anonymize:
            self._anonymize(data, urn)

        # out of an abundance of caution, check that we're not returning one of our own credential values
        for log in data["http_logs"]:
            for secret in self.channel.type.get_redact_values(self.channel):
                assert (
                    secret not in log["url"] and secret not in log["request"] and secret not in log.get("response", "")
                )

        return data

    def _anonymize(self, data: dict, urn):
        request_keys = self.channel.type.redact_request_keys
        response_keys = self.channel.type.redact_response_keys

        for http_log in data["http_logs"]:
            http_log["url"] = self._anonymize_value(http_log["url"], urn)
            http_log["request"] = self._anonymize_value(http_log["request"], urn, redact_keys=request_keys)
            http_log["response"] = self._anonymize_value(http_log.get("response", ""), urn, redact_keys=response_keys)

        for err in data["errors"]:
            err["message"] = self._anonymize_value(err["message"], urn)

    def _anonymize_value(self, original: str, urn, redact_keys=()) -> str:
        # if log doesn't have an associated URN then we don't know what to anonymize, so redact completely
        if not original:
            return ""
        if not urn:
            return original[:10] + self.REDACT_MASK

        if redact_keys:
            redacted = redact.http_trace(original, urn.path, self.REDACT_MASK, redact_keys)
        else:
            redacted = redact.text(original, urn.path, self.REDACT_MASK)

        # if nothing was redacted, don't risk returning sensitive information we didn't find
        if original == redacted and original:
            return original[:10] + self.REDACT_MASK

        return redacted

    def __repr__(self):  # pragma: no cover
        return f"<ChannelLog: uuid={self.uuid} type={self.log_type}>"


class SyncEvent(models.Model):
    """
    A record of a sync from an Android channel
    """

    SOURCE_AC = "AC"
    SOURCE_USB = "USB"
    SOURCE_WIRELESS = "WIR"
    SOURCE_BATTERY = "BAT"
    SOURCE_CHOICES = (
        (SOURCE_AC, "A/C"),
        (SOURCE_USB, "USB"),
        (SOURCE_WIRELESS, "Wireless"),
        (SOURCE_BATTERY, "Battery"),
    )

    STATUS_UNKNOWN = "UNK"
    STATUS_CHARGING = "CHA"
    STATUS_DISCHARGING = "DIS"
    STATUS_NOT_CHARGING = "NOT"
    STATUS_FULL = "FUL"
    STATUS_CHOICES = (
        (STATUS_UNKNOWN, "Unknown"),
        (STATUS_CHARGING, "Charging"),
        (STATUS_DISCHARGING, "Discharging"),
        (STATUS_NOT_CHARGING, "Not Charging"),
        (STATUS_FULL, "Full"),
    )

    channel = models.ForeignKey(Channel, related_name="sync_events", on_delete=models.PROTECT)

    # power status of the device
    power_source = models.CharField(max_length=64, choices=SOURCE_CHOICES)
    power_status = models.CharField(max_length=64, choices=STATUS_CHOICES, default=STATUS_UNKNOWN)
    power_level = models.IntegerField()

    network_type = models.CharField(max_length=128)

    # counts of what was synced
    pending_message_count = models.IntegerField(default=0)
    retry_message_count = models.IntegerField(default=0)
    incoming_command_count = models.IntegerField(default=0)
    outgoing_command_count = models.IntegerField(default=0)

    created_on = models.DateTimeField(default=timezone.now)

    @classmethod
    def create(cls, channel, cmd, incoming_commands):
        # update country, device and OS on our channel
        device = cmd.get("dev", None)
        os = cmd.get("os", None)

        # update our channel if anything is new
        if channel.device != device or channel.os != os:  # pragma: no cover
            channel.device = device
            channel.os = os
            channel.save(update_fields=["device", "os"])

        sync_event = SyncEvent.objects.create(
            channel=channel,
            power_source=cmd.get("p_src", cmd.get("power_source")),
            power_status=cmd.get("p_sts", cmd.get("power_status")),
            power_level=cmd.get("p_lvl", cmd.get("power_level")),
            network_type=cmd.get("net", cmd.get("network_type")),
            pending_message_count=len(cmd.get("pending", cmd.get("pending_messages"))),
            retry_message_count=len(cmd.get("retry", cmd.get("retry_messages"))),
            incoming_command_count=max(len(incoming_commands) - 2, 0),
        )

        sync_event.pending_messages = cmd.get("pending", cmd.get("pending_messages"))
        sync_event.retry_messages = cmd.get("retry", cmd.get("retry_messages"))

        return sync_event

    def get_pending_messages(self):
        return getattr(self, "pending_messages", [])

    def get_retry_messages(self):
        return getattr(self, "retry_messages", [])

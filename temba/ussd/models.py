"""
Written by Keeya Emmanuel Lubowa
On 24th Aug, 2022
Email ekeeya@oddjobs.tech
"""
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.authtoken.models import Token
from smartmin.models import SmartModel
from django.core.paginator import Paginator

from temba.channels.models import Channel
from temba.utils.ussd import AuthSignature

from temba.utils.uuid import uuid4

STARTS_WITH = 1
ENDS_WITH = 2
IS_IN_RESPONSE_BODY = 3
IS_IN_HEADER_XML_JSON = 4
IS_IN_HEADER_PLAIN_TEXT = 5

SIGNAL_CHOICES = (
    (STARTS_WITH, _("Starts With (Plain Text)")),
    (ENDS_WITH, _("Ends With (Plain Text)")),
    (IS_IN_RESPONSE_BODY, _("Is In Response (XML/JSON)")),
    (IS_IN_HEADER_XML_JSON, _("Is in Headers (XML/JSON)")),
    (IS_IN_HEADER_PLAIN_TEXT, _("Is in Headers (Plain Text)"))
)

NONE = "NONE"
TOKEN = "TOKEN"
JWT = "JWT"
BASIC = "BASIC"

AUTH_SCHEMES = [
    (NONE, "NONE"),
    (TOKEN, "TOKEN"),
    (JWT, "JWT"),
    (BASIC, "BASIC")
]

IN_PROGRESS = 'P'
TIMED_OUT = 'TO'
COMPLETED = "C"
TERMINATED = "T"

SESSION_STATUS_CHOICES = (
    (IN_PROGRESS, "In Progress"),
    (TIMED_OUT, "Timed Out"),
    (COMPLETED, "Completed"),
    (TERMINATED, "Terminated")
)


class Handler(SmartModel):
    uuid = models.UUIDField(unique=True, default=uuid4)
    aggregator = models.CharField(
        max_length=150,
        verbose_name=_("Aggregator"),
        help_text=_("Your USSD aggregator"),
    )

    channel = models.ForeignKey(
        Channel, on_delete=models.PROTECT,
        verbose_name=_("USSD Channel"),
        help_text=_("Select any channel of 'External API' Type you would want this handler to use."),
    )

    short_code = models.CharField(
        max_length=50,
        unique=True,
        null=False,
        help_text=_("The USSD shortcode sent by the aggregator in the request."),
        verbose_name=_("Short code")
    )

    request_structure = models.TextField(
        null=False,
        help_text=_("The format of the request string from aggregator's USSD API e.g. in format {{from=msisdn}}")
    )

    signal_exit_or_reply_mode = models.IntegerField(
        verbose_name=_("Menu Type Flag Mode"),
        default=IS_IN_RESPONSE_BODY,
        choices=SIGNAL_CHOICES,
        help_text=_("This indicates how the menu type signal flag/word will be sent back to the aggregator")
    )

    signal_header_key = models.CharField(
        max_length=20,
        verbose_name=_("Menu Type Header name"),
        help_text=_("Represents header whose value is the menu type flag if mode is Is In Headers"),
        null=True,
        blank=True,
    )

    response_structure = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Response Structure"),
        help_text=_("The structure of the response as expected by the aggregator API")
    )

    signal_menu_type_strings = models.CharField(
        max_length=20,
        verbose_name=_("Signal Exit/Wait-Response Flag"),
        help_text=_("Comma-separated key words that indicate which menu type end-user receives e.g END,CON"),
        null=True,
        blank=True,
    )

    auth_scheme = models.CharField(
        max_length=30,
        verbose_name=_("Authentication Scheme"),
        help_text=_("Authentication scheme with which aggregators must authenticate with when calling your callback"),
        choices=AUTH_SCHEMES,
        default=NONE)

    trigger_word = models.CharField(
        max_length=50,
        default="USSD",
        help_text=_("This will trigger execution of a given flow")
    )
    enable_repeat_current_step = models.BooleanField(
        default=False,
        help_text=_("Continue from current step in the flow even with a new USSD session")
    )

    expire_on_inactivity_of = models.IntegerField(
        default=300,
        verbose_name=_(""),
        editable=False,
        help_text=_("Expire all contacts out of their flows, when handler is idle for these seconds")
    )  # 5 minutes
    last_accessed_at = models.DateTimeField(default=timezone.now, editable=False)
    auth_token = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        editable=False
    )

    @property
    def generate_user_token(self):
        user, created = User.objects.get_or_create(username=str(self.uuid))
        token, ct = Token.objects.get_or_create(user=user)
        return token

    def save(self, *args, **kwargs):
        if self.auth_scheme == TOKEN:
            self.auth_token = self.generate_user_token.key
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.aggregator} ({self.short_code})"
 
    class Meta:
        ordering = ["-id"]


class ContactManager(models.Manager):
    def get_contact_object_or_404(self, field, value):
        try:
            if field == 'urn':
                return super(ContactManager, self).get_queryset().get(urn=value)
            else:
                return super(ContactManager, self).get_queryset().get(pk=value)
        except:
            return None

    def delete_contact_by_urn(self, urn):
        contact = self.get_contact_object_or_404('urn', urn)
        if contact:
            contact.delete()


class USSDContact(models.Model):
    urn = models.CharField(max_length=25, unique=True)
    created_on = models.DateTimeField(auto_now_add=True, db_index=True)

    contacts = ContactManager()
    objects = models.Manager()

    def __str__(self):
        return self.urn

    class Meta:
        db_table = 'ussd_contact'


class SessionStatusManager(models.Manager):

    def all_sessions(self, paginate=True, count=10, ):
        objects = super().get_queryset().all().order_by("-last_access_at")
        if paginate:
            return objects
        return Paginator(objects, count).object_list

    def session_by_statuses(self, statuses: list):
        return super().get_queryset().filter(status__in=statuses)

    def sessions_by_fields(self, query_params: dict):
        return super().get_queryset().filter(**query_params)

    def session_by_fields(self, query_params: dict):
        try:
            return super(SessionStatusManager, self).get_queryset().filter(**query_params).latest('created_on')
        except:
            return False


class Session(AuthSignature):
    session_id = models.CharField(
        max_length=100,
        unique=True
    )
    contact = models.ForeignKey(
        USSDContact, on_delete=models.CASCADE
    )
    handler = models.ForeignKey(
        Handler,
        on_delete=models.CASCADE
    )
    status = models.CharField(
        max_length=5,
        choices=SESSION_STATUS_CHOICES,
        default=IN_PROGRESS
    )
    badge = models.CharField(
        max_length=15,
        default='info'
    )

    sessions = SessionStatusManager()
    objects = models.Manager()

    def __str__(self):
        return self.session_id

    class Meta:
        ordering = ['-created_on']

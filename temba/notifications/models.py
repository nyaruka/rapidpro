from abc import abstractmethod

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from temba.channels.models import Channel
from temba.contacts.models import ContactImport, ExportContactsTask
from temba.flows.models import ExportFlowResultsTask
from temba.msgs.models import ExportMessagesTask
from temba.orgs.models import Org


class NotificationType:
    slug = None

    @abstractmethod
    def get_target_url(self, notification) -> str:  # pragma: no cover
        pass

    def as_json(self, notification) -> dict:
        return {
            "type": notification.type.slug,
            "created_on": notification.created_on.isoformat(),
            "target_url": self.get_target_url(notification),
            "is_seen": notification.is_seen,
        }


class ChannelAlertNotificationType(NotificationType):
    slug = "channel:alert"

    def get_target_url(self, notification) -> str:
        return reverse("channels.channel_read", kwargs={"uuid": notification.channel.uuid})

    def as_json(self, notification) -> dict:
        json = super().as_json(notification)
        json["channel"] = {"uuid": str(notification.channel.uuid), "name": notification.channel.name}
        return json


class ExportFinishedNotificationType(NotificationType):
    slug = "export:finished"

    def get_target_url(self, notification) -> str:
        return self._get_export(notification).get_download_url()

    def as_json(self, notification) -> dict:
        export = self._get_export(notification)

        json = super().as_json(notification)
        json["export"] = {"type": export.notification_export_type}
        return json

    @staticmethod
    def _get_export(notification):
        return notification.contact_export or notification.message_export or notification.results_export


class ImportFinishedNotificationType(NotificationType):
    slug = "import:finished"

    def get_target_url(self, notification) -> str:
        return reverse("contacts.contactimport_read", args=[notification.contact_import.id])

    def as_json(self, notification) -> dict:
        json = super().as_json(notification)
        json["import"] = {"num_records": notification.contact_import.num_records}
        return json


class TicketsOpenedNotificationType(NotificationType):
    slug = "tickets:opened"

    def get_target_url(self, notification) -> str:
        return "/ticket/unassigned/"


class TicketActivityNotificationType(NotificationType):
    slug = "tickets:activity"

    def get_target_url(self, notification) -> str:
        return "/ticket/mine/"


TYPES_BY_SLUG = {lt.slug: lt() for lt in NotificationType.__subclasses__()}


class Notification(models.Model):
    """
    A user specific notification
    """

    id = models.BigAutoField(primary_key=True)
    org = models.ForeignKey(Org, on_delete=models.PROTECT, related_name="notifications")
    notification_type = models.CharField(max_length=16, null=True)

    # The scope is what we maintain uniqueness of unseen notifications for within an org. For some notification types,
    # user can only have one unseen of that type per org, and so this will be an empty string. For other notification
    # types like channel alerts, it will be the UUID of an object.
    scope = models.CharField(max_length=36)

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="notifications")
    is_seen = models.BooleanField(default=False)
    created_on = models.DateTimeField(default=timezone.now)

    channel = models.ForeignKey(Channel, null=True, on_delete=models.PROTECT, related_name="notifications")
    contact_export = models.ForeignKey(
        ExportContactsTask, null=True, on_delete=models.PROTECT, related_name="notifications"
    )
    message_export = models.ForeignKey(
        ExportMessagesTask, null=True, on_delete=models.PROTECT, related_name="notifications"
    )
    results_export = models.ForeignKey(
        ExportFlowResultsTask, null=True, on_delete=models.PROTECT, related_name="notifications"
    )
    contact_import = models.ForeignKey(
        ContactImport, null=True, on_delete=models.PROTECT, related_name="notifications"
    )

    @classmethod
    def channel_alert(cls, alert):
        """
        Creates a new channel alert notification for each org admin if there they don't already have an unread one for
        the channel.
        """
        org = alert.channel.org
        cls._create_all(
            org,
            ChannelAlertNotificationType.slug,
            scope=str(alert.channel.uuid),
            users=org.get_admins(),
            channel=alert.channel,
        )

    @classmethod
    def export_finished(cls, export):
        """
        Creates an export finished notification for the creator of the given export.
        """

        cls._create_all(
            export.org,
            ExportFinishedNotificationType.slug,
            scope=export.get_notification_scope(),
            users=[export.created_by],
            **{export.notification_export_type + "_export": export},
        )

    @classmethod
    def _create_all(cls, org, notification_type: str, *, scope: str, users, **kwargs):
        for user in users:
            cls.objects.get_or_create(
                org=org,
                notification_type=notification_type,
                scope=scope,
                user=user,
                is_seen=False,
                defaults=kwargs,
            )

    @classmethod
    def mark_seen(cls, org, notification_type: str, *, scope: str, user):
        cls.objects.filter(
            org_id=org.id, notification_type=notification_type, scope=scope, user=user, is_seen=False
        ).update(is_seen=True)

    @property
    def type(self):
        return TYPES_BY_SLUG[self.notification_type]

    def as_json(self) -> dict:
        return self.type.as_json(self)

    class Meta:
        indexes = [
            # used to list org specific notifications for a user
            models.Index(fields=["org", "user", "-created_on"]),
        ]
        constraints = [
            # used to check if we already have existing unseen notifications for something or to clear unseen
            # notifications when visiting their target URL
            models.UniqueConstraint(
                name="notifications_unseen_of_type",
                fields=["org", "notification_type", "scope", "user"],
                condition=Q(is_seen=False),
            ),
        ]

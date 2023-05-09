import logging
import mimetypes
import os
import re
from array import array
from dataclasses import dataclass
from fnmatch import fnmatch
from urllib.parse import unquote, urlparse

import iso8601
from xlsxlite.writer import XLSXBook

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.core.files.storage import default_storage
from django.core.files.temp import NamedTemporaryFile
from django.db import models
from django.db.models import Prefetch, Q, Sum
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from temba import mailroom
from temba.assets.models import register_asset_store
from temba.channels.models import Channel
from temba.contacts.models import Contact, ContactGroup, ContactURN
from temba.orgs.models import DependencyMixin, Org
from temba.schedules.models import Schedule
from temba.utils import chunk_list, on_transaction_commit
from temba.utils.export import BaseExportAssetStore, BaseItemWithContactExport
from temba.utils.models import JSONAsTextField, SquashableModel, TembaModel
from temba.utils.s3 import public_file_storage
from temba.utils.uuid import uuid4

logger = logging.getLogger(__name__)


class Media(models.Model):
    """
    An uploaded media file that can be used as an attachment on messages.
    """

    ALLOWED_CONTENT_TYPES = ("image/*", "audio/*", "video/*", "application/pdf")
    MAX_UPLOAD_SIZE = 1024 * 1024 * 25  # 25MB

    STATUS_PENDING = "P"
    STATUS_READY = "R"
    STATUS_FAILED = "F"
    STATUS_CHOICES = ((STATUS_PENDING, "Pending"), (STATUS_READY, "Ready"), (STATUS_FAILED, "Failed"))

    uuid = models.UUIDField(default=uuid4, unique=True)
    org = models.ForeignKey(Org, on_delete=models.PROTECT, related_name="media")
    url = models.URLField(max_length=2048)
    content_type = models.CharField(max_length=255)
    path = models.CharField(max_length=2048)
    size = models.IntegerField(default=0)  # bytes
    original = models.ForeignKey("self", null=True, on_delete=models.CASCADE, related_name="alternates")
    status = models.CharField(max_length=1, default=STATUS_PENDING, choices=STATUS_CHOICES)

    # fields that will be set after upload by a processing task
    duration = models.IntegerField(default=0)  # milliseconds
    width = models.IntegerField(default=0)  # pixels
    height = models.IntegerField(default=0)  # pixels

    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_on = models.DateTimeField(default=timezone.now)

    @classmethod
    def is_allowed_type(cls, content_type: str) -> bool:
        for allowed_type in cls.ALLOWED_CONTENT_TYPES:
            if fnmatch(content_type, allowed_type):
                return True
        return False

    @classmethod
    def get_storage_path(cls, org, uuid, filename):
        """
        Returns the storage path for the given filename. Differs slightly from that used by the media endpoint because
        it preserves the original filename which courier still needs if there's no media record for an attachment URL.
        """
        return f"{settings.STORAGE_ROOT_DIR}/{org.id}/media/{str(uuid)[0:4]}/{uuid}/{filename}"

    @classmethod
    def clean_name(cls, filename: str, content_type: str) -> str:
        base_name, extension = os.path.splitext(filename)
        base_name = re.sub(r"[^\w\-\[\]\(\) ]", "", base_name).strip()[:255] or "file"

        if not extension or len(extension) < 2 or not extension[1:].isalnum():
            extension = mimetypes.guess_extension(content_type) or ".bin"

        return base_name + extension

    @classmethod
    def from_upload(cls, org, user, file, process=True):
        """
        Creates a new media instance from a file upload.
        """

        from .tasks import process_media_upload

        assert cls.is_allowed_type(file.content_type), "unsupported content type"

        filename = cls.clean_name(file.name, file.content_type)

        # browsers might send m4a files but correct MIME type is audio/mp4
        if filename.endswith(".m4a"):
            file.content_type = "audio/mp4"

        media = cls._create(org, user, filename, file.content_type, file)

        if process:
            on_transaction_commit(lambda: process_media_upload.delay(media.id))

        return media

    @classmethod
    def create_alternate(cls, original, filename: str, content_type: str, file, **kwargs):
        """
        Creates a new alternate media instance for the given original.
        """

        return cls._create(
            original.org,
            original.created_by,
            filename,
            content_type,
            file,
            original=original,
            status=cls.STATUS_READY,
            **kwargs,
        )

    @classmethod
    def _create(cls, org, user, filename: str, content_type: str, file, **kwargs):
        uuid = uuid4()
        path = cls.get_storage_path(org, uuid, filename)
        path = public_file_storage.save(path, file)
        size = public_file_storage.size(path)

        return cls.objects.create(
            uuid=uuid,
            org=org,
            url=public_file_storage.url(path),
            content_type=content_type,
            path=path,
            size=size,
            created_by=user,
            **kwargs,
        )

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)

    def process_upload(self):
        from .media import process_upload

        assert self.status == self.STATUS_PENDING, "media file is already processed"
        assert not self.original, "only original uploads can be processed"

        process_upload(self)

    def __str__(self) -> str:
        return f"{self.content_type}:{self.url}"

    class Meta:
        indexes = [
            models.Index(name="media_originals_by_org", fields=["org", "-created_on"], condition=Q(original=None))
        ]


class Broadcast(models.Model):
    """
    A broadcast is a message that is sent out to more than one recipient, such
    as a ContactGroup or a list of Contacts. It's nothing more than a way to tie
    messages sent from the same bundle together
    """

    STATUS_QUEUED = "Q"
    STATUS_SENT = "S"
    STATUS_FAILED = "F"
    STATUS_CHOICES = ((STATUS_QUEUED, "Queued"), (STATUS_SENT, "Sent"), (STATUS_FAILED, "Failed"))

    org = models.ForeignKey(Org, on_delete=models.PROTECT)

    # recipients of this broadcast
    groups = models.ManyToManyField(ContactGroup, related_name="addressed_broadcasts")
    contacts = models.ManyToManyField(Contact, related_name="addressed_broadcasts")
    urns = ArrayField(models.TextField(), null=True)
    query = models.TextField(null=True)

    # message content in different languages, e.g. {"eng": {"text": "Hello", "attachments": [...]}, "spa": ...}
    translations = models.JSONField()
    base_language = models.CharField(max_length=3)  # ISO-639-3

    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    created_by = models.ForeignKey(User, null=True, on_delete=models.PROTECT, related_name="broadcast_creations")
    created_on = models.DateTimeField(default=timezone.now)
    modified_by = models.ForeignKey(User, null=True, on_delete=models.PROTECT, related_name="broadcast_modifications")
    modified_on = models.DateTimeField(default=timezone.now)

    # used for scheduled broadcasts which are never actually sent themselves but spawn child broadcasts which are
    schedule = models.OneToOneField(Schedule, on_delete=models.PROTECT, null=True, related_name="broadcast")
    parent = models.ForeignKey("Broadcast", on_delete=models.PROTECT, null=True, related_name="children")
    is_active = models.BooleanField(null=True, default=True)

    @classmethod
    def create(
        cls,
        org,
        user,
        text: dict[str, str] = None,
        *,
        attachments: dict[str, list] = None,
        base_language: str = None,
        groups=None,
        contacts=None,
        urns: list[str] = None,
        contact_ids: list[int] = None,
        **kwargs,
    ):
        # if base language is not provided
        if not base_language:
            base_language = (text and next(iter(text))) or (attachments and next(iter(attachments)))

        assert not text or base_language in text, "no translation for base language"
        assert not attachments or base_language in attachments, "no translation for base language"

        assert text or attachments, "can't create broadcast without text or attachments"
        assert groups or contacts or contact_ids or urns, "can't create broadcast without recipients"

        # merge text and attachments into single dict of translations
        translations = {}
        if text:
            translations = {lang: {"text": t} for lang, t in text.items()}
        if attachments:
            for lang, atts in attachments.items():
                if lang not in translations:
                    translations[lang] = {}

                # TODO update broadcast sending to allow media objects to stay as UUIDs for longer
                translations[lang]["attachments"] = [str(m) for m in atts]

        broadcast = cls.objects.create(
            org=org,
            translations=translations,
            base_language=base_language,
            created_by=user,
            modified_by=user,
            **kwargs,
        )

        # set our recipients
        broadcast._set_recipients(groups=groups, contacts=contacts, urns=urns, contact_ids=contact_ids)

        return broadcast

    def send_async(self):
        """
        Queues this broadcast for sending by mailroom
        """
        mailroom.queue_broadcast(self)

    def has_pending_fire(self):  # pragma: needs cover
        return self.schedule and self.schedule.next_fire is not None

    def get_messages(self):
        return self.msgs.all()

    def get_message_count(self):
        return BroadcastMsgCount.get_count(self)

    def get_translation(self, contact=None) -> dict:
        """
        Gets a translation to use to display this broadcast. If contact is provided and their language is a valid flow
        language and there's a translation for it then that will be used.
        """

        def trans(d):
            return {"text": "", "attachments": []} | d  # ensure we always have text+attachments

        if contact and contact.language and contact.language in self.org.flow_languages:  # try contact language
            if contact.language in self.translations:
                return trans(self.translations[contact.language])

        if self.org.flow_languages[0] in self.translations:  # try org primary language
            return trans(self.translations[self.org.flow_languages[0]])

        return trans(self.translations[self.base_language])  # should always be a base language translation

    def delete(self, user, *, soft: bool):
        if soft:
            assert self.schedule, "can only soft delete scheduled broadcasts"

            self.schedule.is_active = False
            self.schedule.save(update_fields=("is_active",))

            self.modified_by = user
            self.modified_on = timezone.now()
            self.is_active = False
            self.save(update_fields=("modified_by", "modified_on", "is_active"))
        else:
            for child in self.children.all():
                child.delete(user, soft=False)

            for msg in self.msgs.all():
                msg.delete()

            BroadcastMsgCount.objects.filter(broadcast=self).delete()

            super().delete()

            if self.schedule:
                self.schedule.delete()

    def update_recipients(self, *, groups=None, contacts=None, urns: list[str] = None):
        """
        Only used to update recipients for scheduled / repeating broadcasts
        """
        # clear our current recipients
        self.groups.clear()
        self.contacts.clear()

        self._set_recipients(groups=groups, contacts=contacts, urns=urns)

    def _set_recipients(self, *, groups=None, contacts=None, urns: list[str] = None, contact_ids=None):
        """
        Sets the recipients which may be contact groups, contacts or contact URNs.
        """
        if groups:
            self.groups.add(*groups)

        if contacts:
            self.contacts.add(*contacts)

        if urns:
            self.urns = urns
            self.save(update_fields=("urns",))

        if contact_ids:
            RelatedModel = self.contacts.through
            for chunk in chunk_list(contact_ids, 1000):
                bulk_contacts = [RelatedModel(contact_id=id, broadcast_id=self.id) for id in chunk]
                RelatedModel.objects.bulk_create(bulk_contacts)

    def __repr__(self):
        return f'<Broadcast: id={self.id} text="{self.get_translation()["text"]}">'

    class Meta:
        indexes = [
            # used by the broadcasts API endpoint
            models.Index(
                name="msgs_broadcasts_api",
                fields=["org", "-created_on", "-id"],
                condition=Q(schedule__isnull=True, is_active=True),
            ),
            # used by the scheduled broadcasts view
            models.Index(
                name="msgs_broadcasts_scheduled",
                fields=["org", "-created_on"],
                condition=Q(schedule__isnull=False, is_active=True),
            ),
            # used to fetch pending broadcasts for the Outbox
            models.Index(
                name="msgs_broadcasts_queued",
                fields=["org", "-created_on"],
                condition=Q(schedule__isnull=True, status="Q", is_active=True),
            ),
        ]


@dataclass
class Attachment:
    """
    Represents a message attachment stored as type:url
    """

    content_type: str
    url: str

    MAX_LEN = 2048
    CONTENT_TYPE_REGEX = re.compile(r"^(image|audio|video|application|geo|unavailable|(\w+/[-+.\w]+))$")

    @classmethod
    def parse(cls, s):
        if ":" in s:
            content_type, url = s.split(":", 1)
            if cls.CONTENT_TYPE_REGEX.match(content_type) and url:
                return cls(content_type, url)

        raise ValueError(f"{s} is not a valid attachment")

    @classmethod
    def parse_all(cls, attachments):
        return [cls.parse(s) for s in attachments] if attachments else []

    @classmethod
    def bulk_delete(cls, attachments):
        for att in attachments:
            parsed = urlparse(att.url)
            default_storage.delete(unquote(parsed.path))

    def as_json(self):
        return {"content_type": self.content_type, "url": self.url}


class Msg(models.Model):
    """
    Messages are either inbound or outbound and can have varying statuses depending on their direction. Generally an
    outbound message will go through the following statuses:

      INITIALIZING > QUEUED > WIRED > SENT > DELIVERED
                            |
                            > ERRORED > FAILED

    Though in practice to save a database update, messages are created in the database as QUEUED, and only if queueing
    to courier fails, put back in INITIALIZING. If things go wrong during sending, they can be put into ERRORED where
    they can be retried. Once they've exceeded the allowed number of errored sends, they become FAILED.

    Inbound messages are simpler:

      PENDING > HANDLED

    They are created in the database as PENDING and updated to HANDLED once they've been handled by the flow engine.
    """

    STATUS_PENDING = "P"  # incoming msg created but not yet handled
    STATUS_HANDLED = "H"  # incoming msg handled
    STATUS_INITIALIZING = "I"  # outgoing msg that hasn't yet been queued
    STATUS_QUEUED = "Q"  # outgoing msg queued to courier for sending
    STATUS_WIRED = "W"  # outgoing msg requested to be sent via channel
    STATUS_SENT = "S"  # outgoing msg having received sent confirmation from channel
    STATUS_DELIVERED = "D"  # outgoing msg having received delivery confirmation from channel
    STATUS_ERRORED = "E"  # outgoing msg which has errored and will be retried
    STATUS_FAILED = "F"  # outgoing msg which has failed permanently
    STATUS_CHOICES = (
        (STATUS_PENDING, _("Pending")),
        (STATUS_HANDLED, _("Handled")),
        (STATUS_INITIALIZING, _("Initializing")),
        (STATUS_QUEUED, _("Queued")),
        (STATUS_WIRED, _("Wired")),
        (STATUS_SENT, _("Sent")),
        (STATUS_DELIVERED, _("Delivered")),
        (STATUS_ERRORED, _("Error")),
        (STATUS_FAILED, _("Failed")),
    )

    VISIBILITY_VISIBLE = "V"
    VISIBILITY_ARCHIVED = "A"
    VISIBILITY_DELETED_BY_USER = "D"
    VISIBILITY_DELETED_BY_SENDER = "X"
    VISIBILITY_CHOICES = (
        (VISIBILITY_VISIBLE, "Visible"),
        (VISIBILITY_ARCHIVED, "Archived"),
        (VISIBILITY_DELETED_BY_USER, "Deleted by user"),
        (VISIBILITY_DELETED_BY_SENDER, "Deleted by sender"),
    )

    DIRECTION_IN = "I"
    DIRECTION_OUT = "O"
    DIRECTION_CHOICES = ((DIRECTION_IN, "Incoming"), (DIRECTION_OUT, "Outgoing"))

    TYPE_INBOX = "I"  # no longer used
    TYPE_FLOW = "F"  # no longer used
    TYPE_TEXT = "T"
    TYPE_VOICE = "V"
    TYPE_CHOICES = (
        (TYPE_TEXT, "Text Message"),
        (TYPE_VOICE, "Voice Message"),
    )

    FAILED_SUSPENDED = "S"
    FAILED_CONTACT = "C"
    FAILED_LOOPING = "L"
    FAILED_ERROR_LIMIT = "E"
    FAILED_TOO_OLD = "O"
    FAILED_NO_DESTINATION = "D"
    FAILED_CHANNEL_REMOVED = "R"
    FAILED_CHOICES = (
        (FAILED_SUSPENDED, _("Workspace suspended")),
        (FAILED_CONTACT, _("Contact is no longer active")),
        (FAILED_LOOPING, _("Looping detected")),  # mailroom checks for this
        (FAILED_ERROR_LIMIT, _("Retry limit reached")),  # courier tried to send but it errored too many times
        (FAILED_TOO_OLD, _("Too old to send")),  # was queued for too long, would be confusing to send now
        (FAILED_NO_DESTINATION, _("No suitable channel found")),  # no compatible channel + URN destination found
        (FAILED_CHANNEL_REMOVED, _("Channel removed")),  # channel removed by user
    )

    MEDIA_GPS = "geo"
    MEDIA_IMAGE = "image"
    MEDIA_VIDEO = "video"
    MEDIA_AUDIO = "audio"
    MEDIA_TYPES = [MEDIA_AUDIO, MEDIA_GPS, MEDIA_IMAGE, MEDIA_VIDEO]

    MAX_TEXT_LEN = settings.MSG_FIELD_SIZE  # max chars allowed in a message
    MAX_ATTACHMENTS = 10  # max attachments allowed in a message

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid4)
    org = models.ForeignKey(Org, on_delete=models.PROTECT, related_name="msgs", db_index=False)

    # message destination
    channel = models.ForeignKey(Channel, on_delete=models.PROTECT, null=True, related_name="msgs")
    contact = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name="msgs", db_index=False)
    contact_urn = models.ForeignKey(ContactURN, on_delete=models.PROTECT, null=True, related_name="msgs")

    # message origin (note that we don't index or constrain flow/ticket so accessing by these is not supported)
    broadcast = models.ForeignKey(Broadcast, on_delete=models.PROTECT, null=True, related_name="msgs")
    flow = models.ForeignKey("flows.Flow", on_delete=models.DO_NOTHING, null=True, db_index=False, db_constraint=False)
    ticket = models.ForeignKey(
        "tickets.Ticket", on_delete=models.DO_NOTHING, null=True, db_index=False, db_constraint=False
    )
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, db_index=False)

    # message content
    text = models.TextField()
    attachments = ArrayField(models.URLField(max_length=Attachment.MAX_LEN), null=True)
    quick_replies = ArrayField(models.CharField(max_length=64), null=True)
    locale = models.CharField(max_length=6, null=True)  # eng, eng-US, por-BR, und etc

    created_on = models.DateTimeField(db_index=True)
    modified_on = models.DateTimeField(null=True, blank=True, auto_now=True)
    sent_on = models.DateTimeField(null=True)
    queued_on = models.DateTimeField(null=True)

    msg_type = models.CharField(max_length=1, choices=TYPE_CHOICES)
    direction = models.CharField(max_length=1, choices=DIRECTION_CHOICES)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    visibility = models.CharField(max_length=1, choices=VISIBILITY_CHOICES, default=VISIBILITY_VISIBLE)

    labels = models.ManyToManyField("Label", related_name="msgs")

    # the number of actual messages the channel sent this as (outgoing only)
    msg_count = models.IntegerField(default=1)

    # sending (outgoing only)
    high_priority = models.BooleanField(null=True)
    error_count = models.IntegerField(default=0)  # number of times this message has errored
    next_attempt = models.DateTimeField(null=True)  # when we'll next retry
    failed_reason = models.CharField(null=True, max_length=1, choices=FAILED_CHOICES)  # why we've failed

    # the id of this message on the other side of its channel
    external_id = models.CharField(max_length=255, null=True)

    metadata = JSONAsTextField(null=True, default=dict)
    log_uuids = ArrayField(models.UUIDField(), null=True)

    def as_archive_json(self):
        """
        Returns this message in the same format as archived by rp-archiver which is based on the API format
        """
        from temba.api.v2.serializers import MsgReadSerializer

        serializer = MsgReadSerializer()

        return {
            "id": self.id,
            "contact": {"uuid": str(self.contact.uuid), "name": self.contact.name},
            "channel": {"uuid": str(self.channel.uuid), "name": self.channel.name} if self.channel else None,
            "flow": {"uuid": str(self.flow.uuid), "name": self.flow.name} if self.flow else None,
            "urn": self.contact_urn.identity if self.contact_urn else None,
            "direction": serializer.get_direction(self),
            "type": serializer.get_type(self),
            "status": serializer.get_status(self),
            "visibility": serializer.get_visibility(self),
            "text": self.text,
            "attachments": [attachment.as_json() for attachment in Attachment.parse_all(self.attachments)],
            "labels": [{"uuid": str(lb.uuid), "name": lb.name} for lb in self.labels.all()],
            "created_on": self.created_on.isoformat(),
            "sent_on": self.sent_on.isoformat() if self.sent_on else None,
        }

    def get_attachments(self):
        """
        Gets this message's attachments parsed into actual attachment objects
        """
        return Attachment.parse_all(self.attachments)

    def handle(self):
        """
        Queues this message to be handled
        """

        mailroom.queue_msg_handling(self)

    def archive(self):
        """
        Archives this message
        """
        assert self.direction == self.DIRECTION_IN

        if self.visibility == self.VISIBILITY_VISIBLE:
            self.visibility = self.VISIBILITY_ARCHIVED
            self.save(update_fields=("visibility", "modified_on"))

    @classmethod
    def archive_all_for_contacts(cls, contacts):
        """
        Archives all incoming messages for the given contacts
        """
        msgs = Msg.objects.filter(direction=cls.DIRECTION_IN, visibility=cls.VISIBILITY_VISIBLE, contact__in=contacts)
        msg_ids = list(msgs.values_list("pk", flat=True))

        # update modified on in small batches to avoid long table lock, and having too many non-unique values for
        # modified_on which is the primary ordering for the API
        for batch in chunk_list(msg_ids, 100):
            Msg.objects.filter(pk__in=batch).update(visibility=cls.VISIBILITY_ARCHIVED, modified_on=timezone.now())

    def restore(self):
        """
        Restores (i.e. un-archives) this message
        """
        assert self.direction == self.DIRECTION_IN

        if self.visibility == self.VISIBILITY_ARCHIVED:
            self.visibility = self.VISIBILITY_VISIBLE
            self.save(update_fields=("visibility", "modified_on"))

    @classmethod
    def apply_action_label(cls, user, msgs, label):
        label.toggle_label(msgs, add=True)

    @classmethod
    def apply_action_unlabel(cls, user, msgs, label):
        label.toggle_label(msgs, add=False)

    @classmethod
    def apply_action_archive(cls, user, msgs):
        for msg in msgs:
            msg.archive()

    @classmethod
    def apply_action_restore(cls, user, msgs):
        for msg in msgs:
            msg.restore()

    @classmethod
    def apply_action_delete(cls, user, msgs):
        cls.bulk_soft_delete(msgs)

    @classmethod
    def apply_action_resend(cls, user, msgs):
        if msgs:
            mailroom.get_client().msg_resend(msgs[0].org.id, [m.id for m in msgs])

    @classmethod
    def bulk_soft_delete(cls, msgs: list):
        """
        Bulk soft deletes the given incoming messages, i.e. clears content and updates its visibility to deleted.
        """

        attachments_to_delete = []

        for msg in msgs:
            assert msg.direction == Msg.DIRECTION_IN, "only incoming messages can be soft deleted"

            attachments_to_delete.extend(msg.get_attachments())

        Attachment.bulk_delete(attachments_to_delete)

        for msg in msgs:
            msg.labels.clear()

        cls.objects.filter(id__in=[m.id for m in msgs]).update(
            text="", attachments=[], visibility=Msg.VISIBILITY_DELETED_BY_USER
        )

    @classmethod
    def bulk_delete(cls, msgs: list):
        """
        Bulk hard deletes the given messages.
        """

        from temba.channels.models import ChannelLog

        attachments_to_delete = []

        for msg in msgs:
            if msg.direction == Msg.DIRECTION_IN:
                attachments_to_delete.extend(msg.get_attachments())

        Attachment.bulk_delete(attachments_to_delete)

        ChannelLog.objects.filter(msg__in=msgs).delete()

        cls.objects.filter(id__in=[m.id for m in msgs]).delete()

    def __str__(self):  # pragma: needs cover
        return self.text

    class Meta:
        indexes = [
            # used by API messages endpoint hence the ordering, and general fetching by org or contact
            models.Index(name="msgs_by_org", fields=["org", "-created_on", "-id"]),
            models.Index(name="msgs_by_contact", fields=["contact", "-created_on", "-id"]),
            # used for finding errored messages to retry
            models.Index(
                name="msgs_outgoing_to_retry",
                fields=["next_attempt", "created_on", "id"],
                condition=Q(direction="O", status__in=("I", "E"), next_attempt__isnull=False),
            ),
            # used by courier to lookup messages by external id
            models.Index(
                name="msgs_by_external_id",
                fields=["channel_id", "external_id"],
                condition=Q(external_id__isnull=False),
            ),
            # used for Inbox view and API folder
            models.Index(
                name="msgs_inbox",
                fields=["org", "-created_on", "-id"],
                condition=Q(
                    direction="I", visibility="V", status="H", flow__isnull=True, msg_type__in=("I", "F", "T")
                ),
            ),
            # used for Flows view and API folder
            models.Index(
                name="msgs_flows",
                fields=["org", "-created_on", "-id"],
                condition=Q(
                    direction="I", visibility="V", status="H", flow__isnull=False, msg_type__in=("I", "F", "T")
                ),
            ),
            # used for Archived view and API folder
            models.Index(
                name="msgs_archived",
                fields=["org", "-created_on", "-id"],
                condition=Q(direction="I", visibility="A", status="H", msg_type__in=("I", "F", "T")),
            ),
            # used for Outbox and Failed views and API folders
            models.Index(
                name="msgs_outbox_and_failed",
                fields=["org", "status", "-created_on", "-id"],
                condition=Q(direction="O", visibility="V", status__in=("I", "Q", "E", "F")),
            ),
            # used for Sent view / API folder (distinct because of the ordering)
            models.Index(
                name="msgs_sent",
                fields=["org", "-sent_on", "-id"],
                condition=Q(direction="O", visibility="V", status__in=("W", "S", "D")),
            ),
            # used for API incoming folder (unpublicized as could be dropped when CasePro is retired)
            models.Index(
                name="msgs_api_incoming", fields=["org", "-modified_on", "-id"], condition=Q(direction="I", status="H")
            ),
        ]
        constraints = [
            models.CheckConstraint(
                name="no_sent_status_without_sent_on",
                check=(~Q(status__in=("W", "S", "D"), sent_on__isnull=True)),
            ),
        ]


class BroadcastMsgCount(SquashableModel):
    """
    Maintains count of how many msgs are tied to a broadcast
    """

    squash_over = ("broadcast_id",)

    broadcast = models.ForeignKey(Broadcast, on_delete=models.PROTECT, related_name="counts", db_index=True)
    count = models.IntegerField(default=0)

    @classmethod
    def get_squash_query(cls, distinct_set):
        sql = """
        WITH deleted as (
            DELETE FROM %(table)s WHERE "broadcast_id" = %%s RETURNING "count"
        )
        INSERT INTO %(table)s("broadcast_id", "count", "is_squashed")
        VALUES (%%s, GREATEST(0, (SELECT SUM("count") FROM deleted)), TRUE);
        """ % {
            "table": cls._meta.db_table
        }

        return sql, (distinct_set.broadcast_id,) * 2

    @classmethod
    def get_count(cls, broadcast):
        return cls.sum(broadcast.counts.all())


class SystemLabel:
    TYPE_INBOX = "I"
    TYPE_FLOWS = "W"
    TYPE_ARCHIVED = "A"
    TYPE_OUTBOX = "O"
    TYPE_SENT = "S"
    TYPE_FAILED = "X"
    TYPE_SCHEDULED = "E"

    TYPE_CHOICES = (
        (TYPE_INBOX, "Inbox"),
        (TYPE_FLOWS, "Flows"),
        (TYPE_ARCHIVED, "Archived"),
        (TYPE_OUTBOX, "Outbox"),
        (TYPE_SENT, "Sent"),
        (TYPE_FAILED, "Failed"),
        (TYPE_SCHEDULED, "Scheduled"),
    )

    @classmethod
    def get_counts(cls, org):
        return SystemLabelCount.get_totals(org)

    @classmethod
    def get_queryset(cls, org, label_type):
        """
        Gets the queryset for the given system label. Any change here needs to be reflected in a change to the db
        trigger used to maintain the label counts.
        """

        if label_type == cls.TYPE_INBOX:
            qs = Msg.objects.filter(
                direction=Msg.DIRECTION_IN,
                visibility=Msg.VISIBILITY_VISIBLE,
                status=Msg.STATUS_HANDLED,
                flow__isnull=True,
                msg_type__in=(Msg.TYPE_INBOX, Msg.TYPE_FLOW, Msg.TYPE_TEXT),
            )
        elif label_type == cls.TYPE_FLOWS:
            qs = Msg.objects.filter(
                direction=Msg.DIRECTION_IN,
                visibility=Msg.VISIBILITY_VISIBLE,
                status=Msg.STATUS_HANDLED,
                flow__isnull=False,
                msg_type__in=(Msg.TYPE_INBOX, Msg.TYPE_FLOW, Msg.TYPE_TEXT),
            )
        elif label_type == cls.TYPE_ARCHIVED:
            qs = Msg.objects.filter(
                direction=Msg.DIRECTION_IN,
                visibility=Msg.VISIBILITY_ARCHIVED,
                status=Msg.STATUS_HANDLED,
                msg_type__in=(Msg.TYPE_INBOX, Msg.TYPE_FLOW, Msg.TYPE_TEXT),
            )
        elif label_type == cls.TYPE_OUTBOX:
            qs = Msg.objects.filter(
                direction=Msg.DIRECTION_OUT,
                visibility=Msg.VISIBILITY_VISIBLE,
                status__in=(Msg.STATUS_INITIALIZING, Msg.STATUS_QUEUED, Msg.STATUS_ERRORED),
            )
        elif label_type == cls.TYPE_SENT:
            qs = Msg.objects.filter(
                direction=Msg.DIRECTION_OUT,
                visibility=Msg.VISIBILITY_VISIBLE,
                status__in=(Msg.STATUS_WIRED, Msg.STATUS_SENT, Msg.STATUS_DELIVERED),
            )
        elif label_type == cls.TYPE_FAILED:
            qs = Msg.objects.filter(
                direction=Msg.DIRECTION_OUT, visibility=Msg.VISIBILITY_VISIBLE, status=Msg.STATUS_FAILED
            )
        elif label_type == cls.TYPE_SCHEDULED:
            qs = Broadcast.objects.filter(is_active=True).exclude(schedule=None)
        else:  # pragma: needs cover
            raise ValueError("Invalid label type: %s" % label_type)

        return qs.filter(org=org)

    @classmethod
    def get_archive_query(cls, label_type: str) -> dict:
        if label_type == cls.TYPE_INBOX:
            return dict(direction="in", visibility="visible", status="handled", flow__isnull=True, type__ne="voice")
        elif label_type == cls.TYPE_FLOWS:
            return dict(direction="in", visibility="visible", status="handled", flow__isnull=False, type__ne="voice")
        elif label_type == cls.TYPE_ARCHIVED:
            return dict(direction="in", visibility="archived", status="handled", type__ne="voice")
        elif label_type == cls.TYPE_OUTBOX:
            return dict(direction="out", visibility="visible", status__in=("initializing", "queued", "errored"))
        elif label_type == cls.TYPE_SENT:
            return dict(direction="out", visibility="visible", status__in=("wired", "sent", "delivered"))
        elif label_type == cls.TYPE_FAILED:
            return dict(direction="out", visibility="visible", status="failed")


class SystemLabelCount(SquashableModel):
    """
    Counts of messages/broadcasts/calls maintained by database level triggers
    """

    squash_over = ("org_id", "label_type", "is_archived")

    org = models.ForeignKey(Org, on_delete=models.PROTECT, related_name="system_labels")
    label_type = models.CharField(max_length=1, choices=SystemLabel.TYPE_CHOICES)
    is_archived = models.BooleanField(default=False)
    count = models.IntegerField(default=0)

    @classmethod
    def get_squash_query(cls, distinct_set):
        sql = """
        WITH deleted as (
            DELETE FROM %(table)s WHERE "org_id" = %%s AND "label_type" = %%s and "is_archived" = %%s RETURNING "count"
        )
        INSERT INTO %(table)s("org_id", "label_type", "is_archived", "count", "is_squashed")
        VALUES (%%s, %%s, %%s, GREATEST(0, (SELECT SUM("count") FROM deleted)), TRUE);
        """ % {
            "table": cls._meta.db_table
        }

        return sql, (distinct_set.org_id, distinct_set.label_type, distinct_set.is_archived) * 2

    @classmethod
    def get_totals(cls, org):
        """
        Gets all system label counts by type for the given org
        """
        counts = cls.objects.filter(org=org, is_archived=False)
        counts = counts.values_list("label_type").annotate(count_sum=Sum("count"))
        counts_by_type = {c[0]: c[1] for c in counts}

        # for convenience, include all label types
        return {lb: counts_by_type.get(lb, 0) for lb, n in SystemLabel.TYPE_CHOICES}

    class Meta:
        index_together = ("org", "label_type")


class Label(TembaModel, DependencyMixin):
    """
    Labels represent both user defined labels and folders of labels. User defined labels that can be applied to messages
    much the same way labels or tags apply to messages in web-based email services.
    """

    MAX_ORG_FOLDERS = 250

    org_limit_key = Org.LIMIT_LABELS

    org = models.ForeignKey(Org, on_delete=models.PROTECT, related_name="msgs_labels")

    # TODO drop
    label_type = models.CharField(max_length=1, null=True)
    folder = models.ForeignKey("Label", on_delete=models.PROTECT, null=True, related_name="children")

    @classmethod
    def create(cls, org, user, name: str):
        assert cls.is_valid_name(name), f"'{name}' is not a valid label name"
        assert not org.msgs_labels.filter(name__iexact=name).exists()

        return cls.objects.create(org=org, name=name, created_by=user, modified_by=user)

    @classmethod
    def create_from_import_def(cls, org, user, definition: dict):
        return cls.create(org, user, definition["name"])

    def get_messages(self):
        return self.msgs.all()

    def get_visible_count(self):
        """
        Returns the count of visible, non-test message tagged with this label
        """

        return LabelCount.get_totals([self])[self]

    def toggle_label(self, msgs, add):
        """
        Adds or removes this label from the given messages
        """

        changed = set()

        for msg in msgs:
            assert msg.direction == Msg.DIRECTION_IN

            # if we are adding the label and this message doesn't have it, add it
            if add:
                if not msg.labels.filter(pk=self.pk):
                    msg.labels.add(self)
                    changed.add(msg.pk)

            # otherwise, remove it if not already present
            else:
                if msg.labels.filter(pk=self.pk):
                    msg.labels.remove(self)
                    changed.add(msg.pk)

        # update modified on all our changed msgs
        Msg.objects.filter(id__in=changed).update(modified_on=timezone.now())

        return changed

    def release(self, user):
        super().release(user)  # releases flow dependencies

        # delete labellings of messages with this label (not the actual messages)
        Msg.labels.through.objects.filter(label=self).delete()

        self.counts.all().delete()

        self.name = self._deleted_name()
        self.is_active = False
        self.modified_by = user
        self.save(update_fields=("name", "is_active", "modified_by", "modified_on"))

    def __str__(self):  # pragma: needs cover
        return self.name

    class Meta:
        constraints = [models.UniqueConstraint("org", Lower("name"), name="unique_label_names")]


class LabelCount(SquashableModel):
    """
    Counts of user labels maintained by database level triggers
    """

    squash_over = ("label_id", "is_archived")

    label = models.ForeignKey(Label, on_delete=models.PROTECT, related_name="counts")
    is_archived = models.BooleanField(default=False)
    count = models.IntegerField(default=0)

    @classmethod
    def get_squash_query(cls, distinct_set):
        sql = """
            WITH deleted as (
                DELETE FROM %(table)s WHERE "label_id" = %%s AND "is_archived" = %%s RETURNING "count"
            )
            INSERT INTO %(table)s("label_id", "is_archived", "count", "is_squashed")
            VALUES (%%s, %%s, GREATEST(0, (SELECT SUM("count") FROM deleted)), TRUE);
            """ % {
            "table": cls._meta.db_table
        }

        return sql, (distinct_set.label_id, distinct_set.is_archived) * 2

    @classmethod
    def get_totals(cls, labels):
        """
        Gets total counts for all the given labels
        """
        counts = (
            cls.objects.filter(label__in=labels, is_archived=False)
            .values_list("label_id")
            .annotate(count_sum=Sum("count"))
        )
        counts_by_label_id = {c[0]: c[1] for c in counts}
        return {lb: counts_by_label_id.get(lb.id, 0) for lb in labels}


class MsgIterator:
    """
    Queryset wrapper to chunk queries and reduce in-memory footprint
    """

    def __init__(self, ids, order_by=None, select_related=None, prefetch_related=None, max_obj_num=1000):
        self._ids = ids
        self._order_by = order_by
        self._select_related = select_related
        self._prefetch_related = prefetch_related
        self._generator = self._setup()
        self.max_obj_num = max_obj_num

    def _setup(self):
        for i in range(0, len(self._ids), self.max_obj_num):
            chunk_queryset = Msg.objects.filter(id__in=self._ids[i : i + self.max_obj_num])

            if self._order_by:
                chunk_queryset = chunk_queryset.order_by(*self._order_by)

            if self._select_related:
                chunk_queryset = chunk_queryset.select_related(*self._select_related)

            if self._prefetch_related:
                chunk_queryset = chunk_queryset.prefetch_related(*self._prefetch_related)

            yield chunk_queryset

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._generator)


class ExportMessagesTask(BaseItemWithContactExport):
    """
    Wrapper for handling exports of raw messages. This will export all selected messages in
    an Excel spreadsheet, adding sheets as necessary to fall within the guidelines of Excel 97
    (the library we depend on requires this) which has column and row size limits.

    When the export is done, we store the file on the server and send an e-mail notice with a
    link to download the results.
    """

    analytics_key = "msg_export"
    notification_export_type = "message"

    label = models.ForeignKey(Label, on_delete=models.PROTECT, null=True)
    system_label = models.CharField(null=True, max_length=1)

    # TODO backfill, for now overridden from base class to make nullable
    start_date = models.DateField(null=True)
    end_date = models.DateField(null=True)

    @classmethod
    def create(cls, org, user, start_date, end_date, system_label=None, label=None, with_fields=(), with_groups=()):
        assert not (label and system_label), "can't specify both label and system label"

        export = cls.objects.create(
            org=org,
            system_label=system_label,
            label=label,
            start_date=start_date,
            end_date=end_date,
            created_by=user,
            modified_by=user,
        )
        export.with_fields.add(*with_fields)
        export.with_groups.add(*with_groups)
        return export

    def _add_msgs_sheet(self, book):
        name = "Messages (%d)" % (book.num_msgs_sheets + 1) if book.num_msgs_sheets > 0 else "Messages"
        sheet = book.add_sheet(name, book.num_msgs_sheets)
        book.num_msgs_sheets += 1

        self.append_row(sheet, book.headers)
        return sheet

    def write_export(self):
        book = XLSXBook()
        book.num_msgs_sheets = 0
        book.headers = (
            ["Date"]
            + self._get_contact_headers()
            + ["Flow", "Direction", "Text", "Attachments", "Status", "Channel", "Labels"]
        )
        book.current_msgs_sheet = self._add_msgs_sheet(book)

        start_date, end_date = self._get_date_range()

        logger.info(f"starting msgs export #{self.id} for org #{self.org.id}")

        for batch in self._get_msg_batches(self.system_label, self.label, start_date, end_date):
            self._write_msgs(book, batch)

            # update modified_on so we can see if an export hangs
            self.modified_on = timezone.now()
            self.save(update_fields=("modified_on",))

        temp = NamedTemporaryFile(delete=True, suffix=".xlsx", mode="wb+")
        book.finalize(to_file=temp)
        temp.flush()
        return temp, "xlsx"

    def _get_msg_batches(self, system_label, label, start_date, end_date):
        from temba.archives.models import Archive
        from temba.flows.models import Flow

        # firstly get msgs from archives
        if system_label:
            where = SystemLabel.get_archive_query(system_label)
        elif label:
            where = {"visibility": "visible", "__raw__": f"'{label.uuid}' IN s.labels[*].uuid[*]"}
        else:
            where = {"visibility": "visible"}

        records = Archive.iter_all_records(self.org, Archive.TYPE_MSG, start_date, end_date, where=where)
        last_created_on = None

        for record_batch in chunk_list(records, 1000):
            matching = []
            for record in record_batch:
                created_on = iso8601.parse_date(record["created_on"])
                if last_created_on is None or last_created_on < created_on:
                    last_created_on = created_on

                matching.append(record)
            yield matching

        if system_label:
            messages = SystemLabel.get_queryset(self.org, system_label)
        elif label:
            messages = label.get_messages()
        else:
            messages = self.org.msgs.filter(visibility=Msg.VISIBILITY_VISIBLE)

        messages = messages.filter(created_on__gte=start_date, created_on__lte=end_date)

        messages = messages.order_by("created_on").using("readonly")
        if last_created_on:
            messages = messages.filter(created_on__gt=last_created_on)

        all_message_ids = array(str("l"), messages.values_list("id", flat=True))

        for msg_batch in MsgIterator(
            all_message_ids,
            order_by=("created_on",),
            select_related=("channel", "contact_urn"),
            prefetch_related=(
                Prefetch("contact", queryset=Contact.objects.only("uuid", "name")),
                Prefetch("flow", queryset=Flow.objects.only("uuid", "name")),
                Prefetch("labels", queryset=Label.objects.only("uuid", "name").order_by("name")),
            ),
        ):
            # convert this batch of msgs to same format as records in our archives
            yield [msg.as_archive_json() for msg in msg_batch]

    def _write_msgs(self, book, msgs):
        # get all the contacts referenced in this batch
        contact_uuids = {m["contact"]["uuid"] for m in msgs}
        contacts = (
            Contact.objects.filter(org=self.org, uuid__in=contact_uuids)
            .select_related("org")
            .prefetch_related("groups")
            .using("readonly")
        )
        contacts_by_uuid = {str(c.uuid): c for c in contacts}

        for msg in msgs:
            contact = contacts_by_uuid.get(msg["contact"]["uuid"])
            flow = msg.get("flow")

            if book.current_msgs_sheet.num_rows >= self.MAX_EXCEL_ROWS:  # pragma: no cover
                book.current_msgs_sheet = self._add_msgs_sheet(book)

            self.append_row(
                book.current_msgs_sheet,
                [iso8601.parse_date(msg["created_on"])]
                + self._get_contact_columns(contact, urn=msg["urn"])
                + [
                    flow["name"] if flow else None,
                    msg["direction"].upper() if msg["direction"] else None,
                    msg["text"],
                    ", ".join(attachment["url"] for attachment in msg["attachments"]),
                    msg["status"],
                    msg["channel"]["name"] if msg["channel"] else "",
                    ", ".join(msg_label["name"] for msg_label in msg["labels"]),
                ],
            )


@register_asset_store
class MessageExportAssetStore(BaseExportAssetStore):
    model = ExportMessagesTask
    key = "message_export"
    directory = "message_exports"
    permission = "msgs.msg_export"
    extensions = ("xlsx",)

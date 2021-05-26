from smartmin.models import SmartModel

from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from temba.channels.models import Channel
from temba.contacts.models import Contact, ContactGroup
from temba.flows.models import Flow
from temba.orgs.models import Org


class Trigger(SmartModel):
    """
    A Trigger is used to start a user in a flow based on an event. For example, triggers might fire for missed calls,
    inbound messages starting with a keyword, or on a repeating schedule.
    """

    TYPE_KEYWORD = "K"
    TYPE_SCHEDULE = "S"
    TYPE_INBOUND_CALL = "V"
    TYPE_MISSED_CALL = "M"
    TYPE_NEW_CONVERSATION = "N"
    TYPE_REFERRAL = "R"
    TYPE_CLOSED_TICKET = "T"
    TYPE_CATCH_ALL = "C"

    TRIGGER_TYPES = (
        (TYPE_KEYWORD, "Keyword Trigger"),
        (TYPE_SCHEDULE, "Schedule Trigger"),
        (TYPE_INBOUND_CALL, "Inbound Call Trigger"),
        (TYPE_MISSED_CALL, "Missed Call Trigger"),
        (TYPE_NEW_CONVERSATION, "New Conversation Trigger"),
        (TYPE_REFERRAL, "Referral Trigger"),
        (TYPE_CLOSED_TICKET, "Closed Ticket"),
        (TYPE_CATCH_ALL, "Catch All Trigger"),
    )

    KEYWORD_MAX_LEN = 16

    MATCH_FIRST_WORD = "F"
    MATCH_ONLY_WORD = "O"

    MATCH_TYPES = (
        (MATCH_FIRST_WORD, _("Message starts with the keyword")),
        (MATCH_ONLY_WORD, _("Message contains only the keyword")),
    )

    EXPORT_TYPE = "trigger_type"
    EXPORT_KEYWORD = "keyword"
    EXPORT_FLOW = "flow"
    EXPORT_GROUPS = "groups"
    EXPORT_CHANNEL = "channel"

    org = models.ForeignKey(Org, on_delete=models.PROTECT, related_name="triggers")

    trigger_type = models.CharField(max_length=1, choices=TRIGGER_TYPES, default=TYPE_KEYWORD)

    is_archived = models.BooleanField(default=False)

    keyword = models.CharField(
        verbose_name=_("Keyword"),
        max_length=KEYWORD_MAX_LEN,
        null=True,
        blank=True,
        help_text=_("Word to match in the message text"),
    )

    referrer_id = models.CharField(
        verbose_name=_("Referrer Id"),
        max_length=255,
        null=True,
        blank=True,
        help_text=_("The referrer id that triggers us"),
    )

    flow = models.ForeignKey(
        Flow,
        on_delete=models.PROTECT,
        verbose_name=_("Flow"),
        help_text=_("Which flow will be started"),
        related_name="triggers",
    )

    groups = models.ManyToManyField(
        ContactGroup,
        verbose_name=_("Groups"),
        help_text=_("The groups to broadcast the flow to"),
        related_name="triggers",
    )

    contacts = models.ManyToManyField(
        Contact, verbose_name=_("Contacts"), help_text=_("Individual contacts to broadcast the flow to")
    )

    schedule = models.OneToOneField(
        "schedules.Schedule",
        on_delete=models.PROTECT,
        verbose_name=_("Schedule"),
        null=True,
        blank=True,
        related_name="trigger",
        help_text=_("Our recurring schedule"),
    )

    match_type = models.CharField(
        max_length=1,
        choices=MATCH_TYPES,
        default=MATCH_FIRST_WORD,
        null=True,
        verbose_name=_("Trigger When"),
        help_text=_("How to match a message with a keyword"),
    )

    channel = models.ForeignKey(
        Channel,
        on_delete=models.PROTECT,
        verbose_name=_("Channel"),
        null=True,
        related_name="triggers",
        help_text=_("The associated channel"),
    )

    @classmethod
    def create(cls, org, user, trigger_type, flow, channel=None, **kwargs):
        trigger = cls.objects.create(
            org=org, trigger_type=trigger_type, flow=flow, channel=channel, created_by=user, modified_by=user, **kwargs
        )

        # archive any conflicts
        trigger.archive_conflicts(user)

        if trigger.channel:
            trigger.channel.get_type().activate_trigger(trigger)

        return trigger

    def trigger_scopes(self):
        """
        Returns keys that represents the scopes that this trigger can operate against (and might conflict with other triggers with)
        """
        groups = ["**"] if not self.groups else [str(g.id) for g in self.groups.all().order_by("id")]
        return [
            "%s_%s_%s_%s" % (self.trigger_type, str(self.channel_id), group, str(self.keyword)) for group in groups
        ]

    def restore(self, user):
        self.modified_by = user
        self.is_archived = False
        self.save()

        # archive any conflicts
        self.archive_conflicts(user)

        if self.channel:
            self.channel.get_type().activate_trigger(self)

    def archive_conflicts(self, user):
        """
        Archives any triggers that conflict with this one
        """

        if self.trigger_type == Trigger.TYPE_SCHEDULE:
            return

        conflicts = self.org.triggers.filter(
            is_active=True, is_archived=False, trigger_type=self.trigger_type
        ).exclude(id=self.id)

        # if this trigger has a keyword, only archive others with the same keyword
        if self.keyword:
            conflicts = conflicts.filter(keyword=self.keyword)

        # if this trigger has a group, only archive others with the same group
        if self.groups.all():  # pragma: needs cover
            conflicts = conflicts.filter(groups__in=self.groups.all())
        else:
            conflicts = conflicts.filter(groups=None)

        # if this trigger has a referrer_id, only archive others with the same referrer_id
        if self.referrer_id:
            conflicts = conflicts.filter(referrer_id__iexact=self.referrer_id)

        # if this trigger has a channel, only archive others with the same channel
        if self.channel:
            conflicts = conflicts.filter(channel=self.channel)

        # archive any conflicting triggers
        conflicts.update(is_archived=True, modified_on=timezone.now(), modified_by=user)

    @classmethod
    def import_triggers(cls, org, user, trigger_defs, same_site=False):
        """
        Import triggers from a list of exported triggers
        """

        for trigger_def in trigger_defs:
            groups = cls._resolve_import_groups(org, user, trigger_def["groups"], same_site)

            flow = Flow.objects.get(org=org, uuid=trigger_def[Trigger.EXPORT_FLOW]["uuid"], is_active=True)

            # see if that trigger already exists
            existing_triggers = Trigger.objects.filter(org=org, trigger_type=trigger_def[Trigger.EXPORT_TYPE])

            if trigger_def[Trigger.EXPORT_KEYWORD]:
                existing_triggers = existing_triggers.filter(keyword__iexact=trigger_def[Trigger.EXPORT_KEYWORD])

            if groups:
                existing_triggers = existing_triggers.filter(groups__in=groups)

            exact_flow_trigger = existing_triggers.filter(flow=flow).order_by("-created_on").first()
            for tr in existing_triggers:
                if not tr.is_archived and tr != exact_flow_trigger:
                    tr.archive(user)

            if exact_flow_trigger:
                if exact_flow_trigger.is_archived:
                    exact_flow_trigger.restore(user)
            else:

                # if we have a channel resolve it
                channel = trigger_def.get(Trigger.EXPORT_CHANNEL, None)  # older exports won't have a channel
                if channel:
                    channel = Channel.objects.filter(uuid=channel, org=org).first()

                trigger = Trigger.objects.create(
                    org=org,
                    trigger_type=trigger_def[Trigger.EXPORT_TYPE],
                    keyword=trigger_def[Trigger.EXPORT_KEYWORD],
                    flow=flow,
                    created_by=user,
                    modified_by=user,
                    channel=channel,
                )

                for group in groups:
                    trigger.groups.add(group)

    @staticmethod
    def _resolve_import_groups(org, user, specs: list, same_site: bool) -> list:
        groups = []
        for group_spec in specs:
            group = None
            if same_site:
                group = ContactGroup.user_groups.filter(org=org, uuid=group_spec["uuid"], is_active=True).first()
            if not group:
                group = ContactGroup.get_user_group_by_name(org, group_spec["name"])
            if not group:
                group = ContactGroup.create_static(org, user, group_spec["name"])

            groups.append(group)

        return groups

    def as_export_def(self):
        """
        The definition of this trigger for export.
        """
        return {
            Trigger.EXPORT_TYPE: self.trigger_type,
            Trigger.EXPORT_KEYWORD: self.keyword,
            Trigger.EXPORT_FLOW: self.flow.as_export_ref(),
            Trigger.EXPORT_GROUPS: [group.as_export_ref() for group in self.groups.all()],
            Trigger.EXPORT_CHANNEL: self.channel.uuid if self.channel else None,
        }

    @classmethod
    def apply_action_delete(cls, user, triggers):
        for trigger in triggers:
            trigger.delete(user)

    def delete(self, *, force: bool = False):
        """
        Deletes this trigger
        """

        if self.channel:
            try:
                self.channel.get_type().deactivate_trigger(self)
            except Exception as e:
                if not force:
                    raise e

        super().delete()

        if self.schedule:
            self.schedule.delete()

    def __str__(self):
        return f'Trigger[type={self.trigger_type}, flow="{self.flow.name}"]'

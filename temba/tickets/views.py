from collections import defaultdict
from datetime import timedelta

from smartmin.views import SmartCRUDL, SmartListView, SmartTemplateView, SmartUpdateView

from django import forms
from django.conf import settings
from django.db import models
from django.db.models import F, Sum, Value
from django.db.models.aggregates import Max
from django.db.models.expressions import RawSQL
from django.db.models.functions import Cast, Lower
from django.http import Http404, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from temba.contacts.models import URN
from temba.msgs.models import Msg
from temba.orgs.models import Org, OrgRole
from temba.orgs.views.base import (
    BaseCreateModal,
    BaseDeleteModal,
    BaseExportModal,
    BaseListView,
    BaseMenuView,
    BaseUpdateModal,
)
from temba.orgs.views.mixins import OrgObjPermsMixin, OrgPermsMixin, RequireFeatureMixin
from temba.users.models import User
from temba.utils import json
from temba.utils.dates import datetime_to_timestamp, timestamp_to_datetime
from temba.utils.db.functions import SplitPart
from temba.utils.export import response_from_workbook
from temba.utils.fields import InputWidget
from temba.utils.uuid import UUID_REGEX, is_uuid
from temba.utils.views.mixins import ChartViewMixin, ComponentFormMixin, ContextMenuMixin, ModalFormMixin, SpaMixin

from .forms import ShortcutForm, TeamForm, TopicForm
from .models import (
    AllFolder,
    MineFolder,
    Shortcut,
    Team,
    Ticket,
    TicketExport,
    TicketFolder,
    Topic,
    TopicFolder,
    UnassignedFolder,
    export_ticket_stats,
)


class ShortcutCRUDL(SmartCRUDL):
    model = Shortcut
    actions = ("create", "update", "delete", "list")

    class Create(BaseCreateModal):
        form_class = ShortcutForm
        success_url = "@tickets.shortcut_list"

        def save(self, obj):
            return Shortcut.create(self.request.org, self.request.user, obj.name, obj.text)

    class Update(BaseUpdateModal):
        form_class = ShortcutForm
        success_url = "@tickets.shortcut_list"

    class Delete(BaseDeleteModal):
        cancel_url = "@tickets.shortcut_list"
        redirect_url = "@tickets.shortcut_list"

    class List(SpaMixin, ContextMenuMixin, BaseListView):
        menu_path = "/ticket/shortcuts"

        def derive_queryset(self, **kwargs):
            return super().derive_queryset(**kwargs).order_by(Lower("name"))

        def build_context_menu(self, menu):
            if self.has_org_perm("tickets.shortcut_create"):
                menu.add_modax(
                    _("New"),
                    "new-shortcut",
                    reverse("tickets.shortcut_create"),
                    title=_("New Shortcut"),
                    as_button=True,
                )


class TopicCRUDL(SmartCRUDL):
    model = Topic
    actions = ("create", "update", "delete")

    class Create(BaseCreateModal):
        form_class = TopicForm
        success_url = "hide"

        def save(self, obj):
            return Topic.create(self.request.org, self.request.user, obj.name)

    class Update(BaseUpdateModal):
        form_class = TopicForm
        success_url = "hide"

    class Delete(BaseDeleteModal):
        cancel_url = "@tickets.ticket_list"

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context["has_tickets"] = self.object.tickets.exists()
            return context

        def get_redirect_url(self, **kwargs):
            return f"/ticket/{self.request.org.default_topic.uuid}/"


class TeamCRUDL(SmartCRUDL):
    model = Team
    actions = ("create", "update", "delete", "list")

    class Create(RequireFeatureMixin, BaseCreateModal):
        require_feature = Org.FEATURE_TEAMS
        form_class = TeamForm
        success_url = "@tickets.team_list"

        def save(self, obj):
            return Team.create(self.request.org, self.request.user, obj.name, topics=self.form.cleaned_data["topics"])

    class Update(BaseUpdateModal):
        form_class = TeamForm
        success_url = "id@orgs.user_team"

    class Delete(BaseDeleteModal):
        cancel_url = "id@orgs.user_team"
        redirect_url = "@tickets.team_list"

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context["has_agents"] = self.object.get_users().exists()
            context["has_invitations"] = self.object.invitations.filter(is_active=True).exists()
            return context

    class List(RequireFeatureMixin, SpaMixin, ContextMenuMixin, BaseListView):
        require_feature = Org.FEATURE_TEAMS
        menu_path = "/settings/teams"

        def derive_queryset(self, **kwargs):
            return super().derive_queryset(**kwargs).order_by(Lower("name"))

        def build_context_menu(self, menu):
            if self.has_org_perm("tickets.team_create") and not self.is_limit_reached():
                menu.add_modax(
                    _("New"), "new-team", reverse("tickets.team_create"), title=_("New Team"), as_button=True
                )

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)

            # annotate each team with its user count
            for team in context["object_list"]:
                team.user_count = team.get_users().count()

            return context


class TicketCRUDL(SmartCRUDL):
    model = Ticket
    actions = (
        "menu",
        "list",
        "folder",
        "update",
        "note",
        "chart",
        "leaderboard",
        "export",
        "analytics",
        "analytics_export",
    )

    class Menu(BaseMenuView):
        def derive_menu(self):
            org = self.request.org
            user = self.request.user
            topics = Topic.get_accessible(org, user).order_by("-is_system", "name")
            counts = {
                MineFolder.slug: Ticket.get_assignee_count(org, user, topics, Ticket.STATUS_OPEN),
                UnassignedFolder.slug: Ticket.get_assignee_count(org, None, topics, Ticket.STATUS_OPEN),
                AllFolder.slug: Ticket.get_status_count(org, topics, Ticket.STATUS_OPEN),
            }

            menu = []
            for folder in TicketFolder.all().values():
                menu.append(
                    {
                        "id": folder.slug,
                        "name": folder.name,
                        "icon": folder.get_icon(counts[folder.slug]),
                        "count": counts[folder.slug],
                        "href": f"/ticket/{folder.slug}/",
                    }
                )

            menu.append(self.create_divider())
            menu.append(
                self.create_menu_item(
                    menu_id="shortcuts",
                    name=_("Shortcuts"),
                    icon="shortcut",
                    count=org.shortcuts.filter(is_active=True).count(),
                    href="tickets.shortcut_list",
                )
            )

            if self.has_org_perm("tickets.ticket_analytics"):
                menu.append(
                    self.create_menu_item(
                        menu_id="analytics",
                        name=_("Analytics"),
                        icon="analytics",
                        href="tickets.ticket_analytics",
                    )
                )

            menu.append(self.create_space())
            menu.append(self.create_modax_button(_("Export"), "tickets.ticket_export", icon="export"))
            if not Topic.is_limit_reached(org):
                menu.append(
                    self.create_modax_button(
                        _("New Topic"), "tickets.topic_create", icon="add", on_submit="refreshMenu()"
                    )
                )

            menu.append(self.create_divider())

            counts = Ticket.get_topic_counts(org, topics, Ticket.STATUS_OPEN)
            for topic in topics:
                menu.append(
                    {
                        "id": topic.uuid,
                        "name": topic.name,
                        "icon": "topic",
                        "count": counts[topic],
                        "href": f"/ticket/{topic.uuid}/",
                    }
                )

            return menu

    class Analytics(SpaMixin, ContextMenuMixin, OrgPermsMixin, SmartTemplateView):
        permission = "tickets.ticket_analytics"
        title = _("Analytics")
        menu_path = "/ticket/analytics"

        def build_context_menu(self, menu):
            menu.add_link(_("Export Raw"), reverse("tickets.ticket_analytics_export"))

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            return context

    class AnalyticsExport(OrgPermsMixin, SmartTemplateView):
        permission = "tickets.ticket_analytics"

        def render_to_response(self, context, **response_kwargs):
            num_days = self.request.GET.get("days", 90)
            today = timezone.now().date()
            workbook = export_ticket_stats(
                self.request.org, today - timedelta(days=num_days), today + timedelta(days=1)
            )

            return response_from_workbook(workbook, f"ticket-stats-{timezone.now().strftime('%Y-%m-%d')}.xlsx")

    class List(SpaMixin, ContextMenuMixin, OrgPermsMixin, SmartListView):
        """
        Placeholder view for the ticketing frontend components which fetch tickets from the folders view below.
        """

        NEW_LIST_TEMPLATE = "tickets/ticket_list_new.html"

        def get_template_names(self):
            if not getattr(self.request, "legacy", False):
                return [self.NEW_LIST_TEMPLATE]

            return super().get_template_names()

        @classmethod
        def derive_url_pattern(cls, path, action):
            folders = "|".join(TicketFolder.all().keys())
            return rf"^ticket/((?P<folder>{folders}|{UUID_REGEX.pattern})/((?P<status>open|closed)/)?((?P<uuid>[a-z0-9\-]+)/)?)?$"

        def derive_menu_path(self):
            folder, status, ticket, in_page = self.tickets_path

            return f"/ticket/{folder.slug}/"

        @cached_property
        def tickets_path(self) -> tuple[TicketFolder, str, Ticket, bool]:
            """
            Returns tuple of folder, status, ticket, and whether that ticket exists in first page of tickets
            """

            org = self.request.org
            user = self.request.user

            # get requested folder, defaulting to Mine
            folder = TicketFolder.from_slug(org, user, self.kwargs.get("folder", MineFolder.slug))
            if not folder:
                raise Http404()

            status_slug = self.kwargs.get("status")  # only legacy URLs include a status
            status = Ticket.STATUS_CLOSED if status_slug == "closed" else Ticket.STATUS_OPEN

            # is the request for a specific ticket? (a malformed uuid is treated as not found)
            if (uuid := self.kwargs.get("uuid")) and is_uuid(uuid):
                # is the ticket in the first page of the current folder?
                first_page_qs = folder.get_queryset(org, user, ordered=True)
                if status_slug:
                    first_page_qs = first_page_qs.filter(status=status)

                for ticket in list(first_page_qs[: TicketCRUDL.Folder.paginate_by]):
                    if str(ticket.uuid) == uuid:
                        return folder, ticket.status, ticket, True

                # if not, see if we can access it in the All or Mine tickets folders and if so switch to that
                mine_folder = TicketFolder.from_slug(org, user, MineFolder.slug)
                all_folder = TicketFolder.from_slug(org, user, AllFolder.slug)
                for fallback in (mine_folder, all_folder):  # don't rebind folder, we fall back to it below
                    if ticket := fallback.get_queryset(org, user, ordered=False).filter(uuid=uuid).first():
                        return fallback, ticket.status, ticket, False

            return folder, status, None, False

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)

            folder, status, ticket, in_page = self.tickets_path

            context["title"] = folder.name
            context["folder"] = str(folder.slug)
            context["status"] = "open" if status == Ticket.STATUS_OPEN else "closed"
            context["has_tickets"] = self.request.org.tickets.exists()
            context["msg_logs_after"] = (timezone.now() - settings.RETENTION_PERIODS["channellog"]).isoformat()
            # serialized for temba-card-layout's settings attribute
            context["card_settings"] = json.dumps(self.request.user.settings.get("contact_cards", {}))
            context["contact_urn_schemes"] = [
                {"value": value, "name": str(label)} for value, label in URN.SCHEME_CHOICES
            ]

            if ticket:
                context["nextUUID" if in_page else "uuid"] = str(ticket.uuid)

            # pass assignee filter to template if provided (a malformed uuid is ignored, same as in Folder)
            assignee_uuid = self.request.GET.get("assignee")
            if assignee_uuid and is_uuid(assignee_uuid) and isinstance(folder, AllFolder):
                context["assignee_uuid"] = assignee_uuid

            # pass agent permission flags to template
            membership = self.request.org.get_membership(self.request.user)
            context["user_role"] = membership.role_code if membership else OrgRole.ADMINISTRATOR.code
            context["can_assign"] = membership.can_assign if membership else True
            context["can_reply_non_own"] = membership.can_reply_non_own if membership else True

            return context

        def build_context_menu(self, menu):
            folder, status, ticket, in_page = self.tickets_path

            if ticket and ticket.status == Ticket.STATUS_OPEN:
                if self.has_org_perm("tickets.ticket_note"):
                    menu.add_modax(
                        _("Add Note"),
                        "add-note",
                        f"{reverse('tickets.ticket_note', args=[ticket.uuid])}",
                    )

                if self.has_org_perm("flows.flow_start"):
                    menu.add_modax(
                        _("Start Flow"),
                        "start-flow",
                        f"{reverse('flows.flow_start')}?c={ticket.contact.uuid}",
                        disabled=True,
                        on_submit="handleFlowStarted()",
                    )

        def get_queryset(self, **kwargs):
            return super().get_queryset(**kwargs).none()

    class Folder(ContextMenuMixin, OrgPermsMixin, SmartTemplateView):
        permission = "tickets.ticket_list"
        paginate_by = 25

        # microsecond timestamp of 9999-12-31 23:59:59 - anything beyond this can't be converted to a datetime
        MAX_CURSOR = 253_402_300_799_000_000

        @classmethod
        def derive_url_pattern(cls, path, action):
            folders = "|".join(TicketFolder.all().keys())
            return rf"^{path}/{action}/(?P<folder>{folders}|{UUID_REGEX.pattern})/((?P<status>open|closed)/)?((?P<uuid>[a-z0-9\-]+))?$"

        @cached_property
        def folder(self) -> TicketFolder:
            folder = TicketFolder.from_slug(self.request.org, self.request.user, self.kwargs["folder"])
            if not folder:
                raise Http404()

            return folder

        def build_context_menu(self, menu):
            if isinstance(self.folder, TopicFolder) and not self.folder.topic.is_system:
                if self.has_org_perm("tickets.topic_update"):
                    menu.add_modax(
                        _("Edit"),
                        "edit-topic",
                        f"{reverse('tickets.topic_update', args=[self.folder.topic.uuid])}",
                        title=_("Edit Topic"),
                        on_submit="handleTopicUpdated()",
                    )
                if self.has_org_perm("tickets.topic_delete"):
                    menu.add_modax(
                        _("Delete"),
                        "delete-topic",
                        f"{reverse('tickets.topic_delete', args=[self.folder.topic.uuid])}",
                        title=_("Delete Topic"),
                    )

        @cached_property
        def assignee(self):
            # filtering by assignee only applies to the All folder, and a malformed uuid is ignored
            assignee_uuid = self.request.GET.get("assignee")
            if assignee_uuid and is_uuid(assignee_uuid) and isinstance(self.folder, AllFolder):
                return User.objects.filter(uuid=assignee_uuid).first()
            return None

        def _get_queryset(self, *, ordered: bool):
            qs = self.folder.get_queryset(self.request.org, self.request.user, ordered=ordered)
            if self.assignee:
                qs = qs.filter(assignee=self.assignee)
            return qs

        def _int_param(self, name: str) -> int:
            """
            Reads an integer query param, ignoring any non-numeric or out of range value so that a bad cursor from a
            client can't break its polling.
            """
            try:
                value = int(self.request.GET.get(name, 0))
            except ValueError:
                return 0

            return value if 0 <= value <= self.MAX_CURSOR else 0

        def get_tickets(self) -> list:
            uuid = self.kwargs.get("uuid", None)
            status_slug = self.kwargs.get("status")
            status = (Ticket.STATUS_OPEN if status_slug == "open" else Ticket.STATUS_CLOSED) if status_slug else None
            after = self._int_param("after")
            before = self._int_param("before")
            before_id = self._int_param("before_id")

            # request for a specific ticket
            if uuid:
                if not is_uuid(uuid):  # malformed uuid can't match anything
                    return []

                qs = self._get_queryset(ordered=True)
                if status:
                    qs = qs.filter(status=status)
                return list(qs.filter(uuid=uuid))

            # all new activity since a previous fetch.. our indexes have status between org/assignee and
            # last_activity_on so status always needs to be constrained - as equality for a status specific
            # fetch, or as both statuses so the planner can still use the index for the merged fetch
            if after:
                after = timestamp_to_datetime(after)
                qs = (
                    self._get_queryset(ordered=False)
                    .filter(last_activity_on__gt=after)
                    .order_by("last_activity_on", "id")
                )
                qs = (
                    qs.filter(status=status)
                    if status
                    else qs.filter(status__in=(Ticket.STATUS_OPEN, Ticket.STATUS_CLOSED))
                )

                # bounded so a long gap in polling can't return the world - the client advances its cursor and
                # polls again so it still catches up
                tickets = list(qs[: self.paginate_by])

                if len(tickets) == self.paginate_by:
                    # the client's cursor only has millisecond resolution (timestamps are serialized to JSON
                    # with milliseconds) so a full page must reach past its last row's millisecond for the
                    # cursor to advance - extend it to that boundary, and if even that doesn't get past the
                    # cursor's own millisecond (a bulk update can put a whole page inside one), don't cap
                    last = tickets[-1].last_activity_on
                    cutoff = last.replace(microsecond=(last.microsecond // 1000) * 1000) + timedelta(milliseconds=1)
                    if cutoff > after + timedelta(milliseconds=1):
                        tickets = list(qs.filter(last_activity_on__lt=cutoff))
                    else:
                        tickets = list(qs)

                return tickets

            # pages are read in index order - open before closed, then most recent activity - and paged by an
            # exact (last_activity_on, id) cursor so that tickets sharing a timestamp can't be lost
            qs = self._get_queryset(ordered=True)
            if status:
                qs = qs.filter(status=status)

            if before and before_id:
                before = timestamp_to_datetime(before)
                if status:
                    cursor = RawSQL(
                        "(tickets_ticket.last_activity_on, tickets_ticket.id) < (%s, %s)",
                        (before, before_id),
                        output_field=models.BooleanField(),
                    )
                else:
                    # a merged cursor is always in the open tickets because next links switch to the closed
                    # URL once a page ends in a closed ticket
                    cursor = RawSQL(
                        "(tickets_ticket.status, tickets_ticket.last_activity_on, tickets_ticket.id) < (%s, %s, %s)",
                        (Ticket.STATUS_OPEN, before, before_id),
                        output_field=models.BooleanField(),
                    )
                qs = qs.filter(cursor)
            elif before and status:
                # kept for any in-flight links from before cursors included ids - only meaningful for a status
                # specific fetch, on the merged fetch a timestamp alone can't say which side of the open/closed
                # boundary it's on so it's ignored and the first page is served
                qs = qs.filter(last_activity_on__lt=timestamp_to_datetime(before))

            return list(qs[: self.paginate_by])

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)

            tickets = self.get_tickets()
            context["tickets"] = tickets

            # get the last message for each contact that these tickets belong to
            contact_ids = {t.contact_id for t in tickets}
            last_msg_ids = Msg.objects.filter(contact_id__in=contact_ids).values("contact").annotate(last_msg=Max("id"))
            last_msgs = Msg.objects.filter(id__in=[m["last_msg"] for m in last_msg_ids]).select_related("created_by")

            context["last_msgs"] = {m.contact_id: m for m in last_msgs}
            return context

        def render_to_response(self, context, **response_kwargs):
            def topic_as_json(t):
                return {"uuid": str(t.uuid), "name": t.name}

            def user_as_json(u):
                return {
                    "id": u.id,
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "email": u.email,
                    "uuid": str(u.uuid),
                }

            def msg_as_json(m):
                return {
                    "text": m.text,
                    "direction": m.direction,
                    "type": m.msg_type,
                    "created_on": m.created_on,
                    "sender": {"id": m.created_by.id, "email": m.created_by.email} if m.created_by else None,
                    "attachments": m.attachments,
                }

            def as_json(t):
                """
                Converts a ticket to the contact-centric format expected by our frontend components
                """
                last_msg = context["last_msgs"].get(t.contact_id)
                return {
                    "uuid": str(t.contact.uuid),
                    "name": t.contact.get_display(org=self.request.org),
                    "last_seen_on": t.contact.last_seen_on,
                    "last_msg": msg_as_json(last_msg) if last_msg else None,
                    "ticket": {
                        "uuid": str(t.uuid),
                        "assignee": user_as_json(t.assignee) if t.assignee else None,
                        "topic": topic_as_json(t.topic) if t.topic else None,
                        "last_activity_on": t.last_activity_on,
                        "closed_on": t.closed_on,
                    },
                }

            results = {"results": [as_json(t) for t in context["tickets"]]}

            # build up our next link if we have more - refreshes (?after=) are never paged because they're ordered
            # oldest first, so a next link from the newest ticket would page backwards from an arbitrary point
            if not self._int_param("after") and len(context["tickets"]) >= self.paginate_by:
                last = context["tickets"][-1]

                # merged paging continues without a status until it crosses into closed tickets
                status_slug = self.kwargs.get("status")
                if not status_slug and last.status == Ticket.STATUS_CLOSED:
                    status_slug = "closed"

                # the status and uuid parts of the pattern are optional so it can only be reversed by folder
                folder_url = reverse("tickets.ticket_folder", kwargs={"folder": self.folder.slug})
                if status_slug:
                    folder_url += f"{status_slug}/"

                next_url = f"{folder_url}?before={datetime_to_timestamp(last.last_activity_on)}&before_id={last.id}"
                if self.assignee:
                    next_url += f"&assignee={self.assignee.uuid}"

                results["next"] = next_url

            return JsonResponse(results)

    class Update(ComponentFormMixin, ModalFormMixin, OrgObjPermsMixin, SmartUpdateView):
        class Form(forms.ModelForm):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)

                self.fields["topic"].queryset = self.instance.org.topics.filter(is_active=True).order_by(
                    "-is_system", "name"
                )

            class Meta:
                fields = ("topic",)
                model = Ticket

        form_class = Form
        fields = ("topic",)
        slug_url_kwarg = "uuid"
        success_url = "hide"

    class Note(ModalFormMixin, ComponentFormMixin, OrgObjPermsMixin, SmartUpdateView):
        """
        Creates a note for this contact
        """

        class Form(forms.ModelForm):
            note = forms.CharField(
                max_length=Ticket.MAX_NOTE_LENGTH,
                required=True,
                widget=InputWidget({"hide_label": True, "textarea": True}),
                help_text=_("Notes can only be seen by the support team"),
            )

            class Meta:
                model = Ticket
                fields = ("note",)

        form_class = Form
        fields = ("note",)
        success_url = "hide"
        slug_url_kwarg = "uuid"

        def form_valid(self, form):
            self.get_object().add_note(self.request.user, note=form.cleaned_data["note"])
            return self.render_modal_response(form)

    class Chart(OrgPermsMixin, ChartViewMixin, SmartTemplateView):
        permission = "tickets.ticket_analytics"
        default_chart_period = (-timedelta(days=90), timedelta(days=1))

        @classmethod
        def derive_url_pattern(cls, path, action):
            return r"^%s/%s/(?P<chart>(opened|resptime|replies))/$" % (path, action)

        def get_opened_chart(self, org, since, until) -> tuple:
            topics_by_id = {t.id: t.name for t in org.topics.filter(is_active=True)}

            counts = org.daily_counts.period(since, until).prefix("tickets:opened:").day_totals(scoped=True)

            # collect all dates and values by topic
            dates_set = set()
            values_by_topic = defaultdict(dict)

            for (day, scope), count in counts.items():
                topic_id = int(scope.split(":")[-1])
                topic_name = topics_by_id.get(topic_id, "<Unknown>")
                dates_set.add(day)
                values_by_topic[topic_name][day] = count

            # create sorted list of dates
            labels = sorted(list(dates_set))

            # create arrays of values for each topic, using 0 for missing dates
            datasets = []
            for topic_name, date_counts in values_by_topic.items():
                datasets.append({"label": topic_name, "data": [date_counts.get(date, 0) for date in labels]})

            return [d.strftime("%Y-%m-%d") for d in labels], datasets

        def get_resptime_chart(self, org, since, until) -> tuple:
            counts = org.daily_counts.period(since, until).prefix("ticketresptime:").day_totals(scoped=True)
            totals_by_date, counts_by_date = {}, {}
            for (day, scope), count in counts.items():
                if scope.endswith(":total"):
                    totals_by_date[day] = count
                elif scope.endswith(":count"):
                    counts_by_date[day] = count

            # collect all dates
            dates_set = set(totals_by_date.keys()) | set(counts_by_date.keys())
            labels = sorted(list(dates_set))

            # calculate averages for each date, use 0 if missing
            data = []
            for d in labels:
                total = totals_by_date.get(d, 0)
                count = counts_by_date.get(d, 0)
                avg = (total // count) if count else 0
                data.append(avg)

            return [d.strftime("%Y-%m-%d") for d in labels], [{"label": _("Response Time"), "data": data}]

        def get_replies_chart(self, org, since, until) -> tuple:
            teams_by_id = {t.id: t.name for t in org.teams.filter(is_active=True)}
            # Add default team (id=0) for users not assigned to specific teams
            teams_by_id[0] = _("No Team")

            # Follow the pattern from get_topic_counts - use database aggregation to extract team_id
            # scope format: msgs:ticketreplies:{team_id}:{user_id} - team_id is at position 3 (1-indexed)
            daily_counts = org.daily_counts.period(since, until).prefix("msgs:ticketreplies:")

            counts = (
                daily_counts.annotate(
                    team_id=Cast(SplitPart(F("scope"), Value(":"), Value(3)), output_field=models.IntegerField())
                )
                .values_list("day", "team_id")
                .annotate(count_sum=Sum("count"))
            )

            # collect all dates and values by team
            dates_set = set()
            values_by_team = defaultdict(lambda: defaultdict(int))

            for day, team_id, count_sum in counts:
                team_name = teams_by_id.get(team_id, f"Team {team_id}")
                dates_set.add(day)
                values_by_team[team_name][day] += count_sum

            # create sorted list of dates
            labels = sorted(list(dates_set))

            # create arrays of values for each team, using 0 for missing dates
            datasets = []
            for team_name in sorted(values_by_team.keys()):
                date_counts = values_by_team[team_name]
                datasets.append({"label": team_name, "data": [date_counts.get(date, 0) for date in labels]})

            return [d.strftime("%Y-%m-%d") for d in labels], datasets

        def get_chart_data(self, since, until) -> tuple[list, list]:
            chart = self.kwargs["chart"]
            if chart == "opened":
                return self.get_opened_chart(self.request.org, since, until)
            elif chart == "resptime":
                return self.get_resptime_chart(self.request.org, since, until)
            elif chart == "replies":
                return self.get_replies_chart(self.request.org, since, until)

    class Leaderboard(OrgPermsMixin, ChartViewMixin, SmartTemplateView):
        permission = "tickets.ticket_analytics"

        def render_to_response(self, context, **response_kwargs):
            org = self.request.org
            since, until = self.get_chart_period()

            daily_counts = org.daily_counts.period(since, until).prefix("msgs:ticketreplies:")

            counts = (
                daily_counts.annotate(
                    user_id=Cast(SplitPart(F("scope"), Value(":"), Value(4)), output_field=models.IntegerField())
                )
                .values("user_id")
                .annotate(replies=Sum("count"))
                .order_by("-replies")
            )

            users_by_id = {u.id: u for u in org.users.all()}

            results = []
            for row in counts:
                user = users_by_id.get(row["user_id"])
                if user:
                    results.append({"name": str(user), "uuid": str(user.uuid), "replies": row["replies"]})

            return JsonResponse({"results": results})

    class Export(BaseExportModal):
        export_type = TicketExport
        success_url = "@tickets.ticket_list"

        def create_export(self, org, user, form):
            start_date = form.cleaned_data["start_date"]
            end_date = form.cleaned_data["end_date"]
            with_fields = form.cleaned_data["with_fields"]
            with_groups = form.cleaned_data["with_groups"]
            return TicketExport.create(
                org, user, start_date, end_date, with_fields=with_fields, with_groups=with_groups
            )

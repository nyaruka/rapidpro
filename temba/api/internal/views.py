from collections import defaultdict
from datetime import date, timedelta

from rest_framework import status
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response

from django.db.models import Prefetch, Q, Sum

from temba.ai.models import LLM
from temba.channels.models import Channel, ChannelCount
from temba.locations.models import AdminBoundary
from temba.notifications.models import Notification
from temba.orgs.models import Org
from temba.templates.models import Template, TemplateTranslation
from temba.tickets.models import Shortcut
from temba.users.models import User

from ..models import APIPermission, SSLPermission
from ..support import (
    APISessionAuthentication,
    CreatedOnCursorPagination,
    InvalidQueryError,
    ModifiedOnCursorPagination,
    NameCursorPagination,
)
from ..views import BaseAPIView, ListAPIMixin
from . import serializers


class BaseEndpoint(BaseAPIView):
    """
    Base class of all our internal API endpoints
    """

    authentication_classes = (APISessionAuthentication,)
    permission_classes = (SSLPermission, APIPermission)


# ============================================================
# Endpoints (A-Z)
# ============================================================


class LLMsEndpoint(ListAPIMixin, BaseEndpoint):
    """
    LLMs for the current user.
    """

    model = LLM
    serializer_class = serializers.LLMReadSerializer
    pagination_class = NameCursorPagination

    def get_queryset(self):
        return super().get_queryset().filter(org=self.request.org, is_active=True)


class LocationsEndpoint(ListAPIMixin, BaseEndpoint):
    """
    Admin boundaries searchable by name at a specified level.
    """

    LEVELS = {
        "state": AdminBoundary.LEVEL_STATE,
        "district": AdminBoundary.LEVEL_DISTRICT,
        "ward": AdminBoundary.LEVEL_WARD,
    }

    class Pagination(CursorPagination):
        ordering = ("name", "id")
        offset_cutoff = 100000

    model = AdminBoundary
    serializer_class = serializers.LocationReadSerializer
    pagination_class = Pagination

    def derive_queryset(self):
        org = self.request.org
        level = self.LEVELS.get(self.request.query_params.get("level"))
        query = self.request.query_params.get("query")

        if not org.country or not level:
            return AdminBoundary.objects.none()

        qs = AdminBoundary.objects.filter(
            path__startswith=f"{org.country.name} {AdminBoundary.PATH_SEPARATOR}", level=level
        )

        if query:
            qs = qs.filter(Q(path__icontains=query))

        return qs.only("osm_id", "name", "path")


class NotificationsEndpoint(ListAPIMixin, BaseEndpoint):
    model = Notification
    pagination_class = CreatedOnCursorPagination
    serializer_class = serializers.ModelAsJsonSerializer

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(org=self.request.org, user=self.request.user, medium__contains=Notification.MEDIUM_UI)
            .prefetch_related("contact_import", "export", "incident")
        )

    def delete(self, request, *args, **kwargs):
        Notification.mark_seen(self.request.org, self.request.user)

        return Response(status=status.HTTP_204_NO_CONTENT)


class OrgsEndpoint(ListAPIMixin, BaseEndpoint):
    """
    Orgs for the current user.
    """

    model = Org
    serializer_class = serializers.OrgReadSerializer
    pagination_class = ModifiedOnCursorPagination

    def get_queryset(self):
        return User.get_orgs_for_request(self.request)


class ShortcutsEndpoint(ListAPIMixin, BaseEndpoint):
    model = Shortcut
    serializer_class = serializers.ShortcutReadSerializer
    pagination_class = ModifiedOnCursorPagination


class StatisticsEndpoint(BaseEndpoint):
    """
    Daily statistics including per-channel message counts.
    """

    model = ChannelCount
    permission = "channels.channel_list"

    IN_SCOPES = (ChannelCount.SCOPE_TEXT_IN, ChannelCount.SCOPE_VOICE_IN)
    OUT_SCOPES = (ChannelCount.SCOPE_TEXT_OUT, ChannelCount.SCOPE_VOICE_OUT)

    def get(self, request, *args, **kwargs):
        today = date.today()
        since = self._parse_date("since", default=today - timedelta(days=90))
        until = self._parse_date("until", default=today + timedelta(days=1))

        if (until - since).days > 365:
            raise InvalidQueryError("Date range can't be more than 365 days.")

        counts = (
            ChannelCount.objects.filter(
                channel__org=request.org,
                channel__is_active=True,
                day__gte=since,
                day__lt=until,
                scope__in=self.IN_SCOPES + self.OUT_SCOPES,
            )
            .values("day", "channel__uuid", "channel__channel_type", "scope")
            .annotate(count_sum=Sum("count"))
            .order_by("day")
        )

        # group by day then channel
        by_day = defaultdict(lambda: defaultdict(lambda: {"type": None, "in": 0, "out": 0}))
        for row in counts:
            day = row["day"]
            ch_uuid = row["channel__uuid"]
            entry = by_day[day][ch_uuid]
            entry["type"] = Channel.get_type_from_code(row["channel__channel_type"]).slug
            if row["scope"] in self.IN_SCOPES:
                entry["in"] += row["count_sum"]
            else:
                entry["out"] += row["count_sum"]

        results = [{"date": day.isoformat(), "channels": dict(channels)} for day, channels in sorted(by_day.items())]

        return Response({"results": results})

    def _parse_date(self, param, default=None):
        value = self.request.query_params.get(param)
        if not value:
            return default
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise InvalidQueryError(f"Invalid date value for '{param}'.")


class TemplatesEndpoint(ListAPIMixin, BaseEndpoint):
    """
    WhatsApp templates with their translations.
    """

    model = Template
    serializer_class = serializers.TemplateReadSerializer
    pagination_class = ModifiedOnCursorPagination

    def filter_queryset(self, queryset):
        org = self.request.org
        queryset = org.templates.exclude(translations=None).prefetch_related(
            Prefetch("translations", TemplateTranslation.objects.order_by("locale")),
            Prefetch("translations__channel", Channel.objects.only("uuid", "name")),
        )
        return self.filter_before_after(queryset, "modified_on").select_related("base_translation__channel")

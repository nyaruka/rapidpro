from uuid import UUID

from rest_framework import status
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response

from django.db.models import Prefetch, Q

from temba.ai.models import LLM
from temba.channels.models import Channel
from temba.contacts.models import Contact, ContactField, ContactGroup
from temba.flows.models import Flow, FlowLabel
from temba.globals.models import Global
from temba.locations.models import AdminBoundary
from temba.msgs.models import OptIn
from temba.notifications.models import Notification
from temba.orgs.models import Org
from temba.templates.models import Template, TemplateTranslation
from temba.tickets.models import Shortcut, Topic
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

        if not org.root_location or not level:
            return AdminBoundary.objects.none()

        qs = AdminBoundary.objects.filter(
            path__startswith=f"{org.root_location.name} {AdminBoundary.PATH_SEPARATOR}", level=level
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


class AssetsEndpoint(BaseEndpoint):
    """
    Resolves flow asset references to their current names.

    The JSON payload maps each supported asset type to a list of identifiers,
    and up to 100 assets can be resolved in one request. UUID-backed
    references return a ``uuid`` while fields and globals return their ``key``.
    Assets which no longer exist or aren't available in the current org are
    omitted.
    """

    permission = "flows.flow_editor"

    UUID_MODELS = {
        "channel": Channel,
        "flow": Flow,
        "group": ContactGroup,
        "label": FlowLabel,
        "llm": LLM,
        "optin": OptIn,
        "template": Template,
        "topic": Topic,
    }
    KEY_MODELS = {"field": ContactField, "global": Global}
    MAX_REFERENCES = 100

    def post(self, request, *args, **kwargs):
        org = request.org
        payload = request.data
        if not isinstance(payload, dict):
            raise InvalidQueryError("Payload must be an object mapping asset types to lists of identifiers.")

        supported_types = {*self.UUID_MODELS, "contact", "user", *self.KEY_MODELS}
        unknown_types = set(payload) - supported_types
        if unknown_types:
            raise InvalidQueryError(f"Unsupported asset type: {sorted(unknown_types)[0]}.")

        requested = {}
        total = 0

        for asset_type in supported_types:
            values = payload.get(asset_type, [])
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                raise InvalidQueryError(f"Asset type '{asset_type}' must be a list of identifiers.")
            requested[asset_type] = values
            total += len(values)

        if total > self.MAX_REFERENCES:
            raise InvalidQueryError(f"A maximum of {self.MAX_REFERENCES} assets can be resolved at once.")

        uuid_types = {*self.UUID_MODELS, "contact", "user"}
        for asset_type in uuid_types:
            values = requested[asset_type]
            try:
                requested[asset_type] = [UUID(value) for value in values]
            except ValueError as error:
                raise InvalidQueryError(f"Asset type '{asset_type}': {error.args[0]}")

        contact_uuids = requested["contact"]
        user_uuids = requested["user"]

        results = []
        for asset_type, model in self.UUID_MODELS.items():
            values = requested[asset_type]
            if not values:
                continue

            queryset = model.objects.filter(org=org, uuid__in=values, is_active=True).using("readonly")

            by_uuid = {str(obj.uuid): obj for obj in queryset.only("uuid", "name")}
            for value in values:
                if obj := by_uuid.get(str(value)):
                    results.append({"type": asset_type, "uuid": str(obj.uuid), "name": obj.name})

        if contact_uuids:
            contacts = list(Contact.objects.filter(org=org, uuid__in=contact_uuids, is_active=True).using("readonly"))
            Contact.bulk_urn_cache_initialize(contacts, using="readonly")
            by_uuid = {str(contact.uuid): contact for contact in contacts}
            for value in contact_uuids:
                if contact := by_uuid.get(str(value)):
                    results.append({"type": "contact", "uuid": str(contact.uuid), "name": contact.get_display(org=org)})

        if user_uuids:
            users = org.get_users().filter(uuid__in=user_uuids).using("readonly")
            by_uuid = {str(user.uuid): user for user in users.only("uuid", "first_name", "last_name")}
            for value in user_uuids:
                if user := by_uuid.get(str(value)):
                    results.append({"type": "user", "uuid": str(user.uuid), "name": user.name})

        for asset_type, model in self.KEY_MODELS.items():
            values = requested[asset_type]
            if not values:
                continue

            by_key = {
                obj.key: obj
                for obj in model.objects.filter(org=org, key__in=values, is_active=True)
                .using("readonly")
                .only("key", "name")
            }
            for value in values:
                if obj := by_key.get(value):
                    results.append({"type": asset_type, "key": obj.key, "name": obj.name})

        return Response({"results": results})


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

    def get_queryset(self):
        return super().get_queryset().filter(org=self.request.org, is_active=True)


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

from collections import namedtuple
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


# how a type of asset reference is resolved: the field which identifies it in flow definitions, a function returning the
# matching objects in an org, and a function returning the name to return for an object
AssetType = namedtuple("AssetType", ("id_field", "fetch", "get_name"))


def _asset_by_field(model, id_field: str, **filters) -> AssetType:
    def fetch(org, values: list):
        qs = model.objects.filter(org=org, is_active=True, **{f"{id_field}__in": values}, **filters)
        return qs.using("readonly").only(id_field, "name")

    return AssetType(id_field, fetch, lambda org, obj: obj.name)


def _fetch_contacts(org, values: list):
    contacts = list(Contact.objects.filter(org=org, uuid__in=values, is_active=True).using("readonly"))
    Contact.bulk_urn_cache_initialize(contacts, using="readonly")
    return contacts


def _fetch_users(org, values: list):
    # email is needed as the display fallback for users without a name
    return org.get_users().filter(uuid__in=values).using("readonly").only("uuid", "first_name", "last_name", "email")


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

    # the supported asset types, in the order in which they're resolved and returned
    ASSET_TYPES = {
        "channel": _asset_by_field(Channel, "uuid"),
        "flow": _asset_by_field(Flow, "uuid"),
        "group": _asset_by_field(
            ContactGroup, "uuid", group_type__in=(ContactGroup.TYPE_MANUAL, ContactGroup.TYPE_SMART)
        ),
        "label": _asset_by_field(FlowLabel, "uuid"),
        "llm": _asset_by_field(LLM, "uuid"),
        "optin": _asset_by_field(OptIn, "uuid"),
        "template": _asset_by_field(Template, "uuid"),
        "topic": _asset_by_field(Topic, "uuid"),
        "contact": AssetType("uuid", _fetch_contacts, lambda org, obj: obj.get_display(org=org)),
        "user": AssetType("uuid", _fetch_users, lambda org, obj: str(obj)),
        "field": _asset_by_field(ContactField, "key"),
        "global": _asset_by_field(Global, "key"),
    }

    # clients chunk their requests to match this, so exceeding it is a client bug rather than something to truncate
    MAX_REFERENCES = 100

    def post(self, request, *args, **kwargs):
        org = request.org
        payload = request.data
        if not isinstance(payload, dict):
            raise InvalidQueryError("Payload must be an object mapping asset types to lists of identifiers.")

        unknown_types = sorted(set(payload) - set(self.ASSET_TYPES))
        if unknown_types:
            raise InvalidQueryError(f"Unsupported asset type: {unknown_types[0]}.")

        requested = {}  # asset type to the identifiers requested for it

        for asset_type in self.ASSET_TYPES:
            values = payload.get(asset_type, [])
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                raise InvalidQueryError(f"Asset type '{asset_type}' must be a list of identifiers.")

            requested[asset_type] = values

        if sum(len(values) for values in requested.values()) > self.MAX_REFERENCES:
            raise InvalidQueryError(f"A maximum of {self.MAX_REFERENCES} assets can be resolved at once.")

        for asset_type, spec in self.ASSET_TYPES.items():
            # normalize UUIDs to their canonical form, and drop duplicates whilst preserving the requested order
            values = requested[asset_type]
            if spec.id_field == "uuid":
                try:
                    values = [str(UUID(value)) for value in values]
                except ValueError as error:
                    raise InvalidQueryError(f"Asset type '{asset_type}': {error.args[0]}")

            requested[asset_type] = list(dict.fromkeys(values))

        results = []
        for asset_type, spec in self.ASSET_TYPES.items():
            values = requested[asset_type]
            if not values:
                continue

            by_id = {str(getattr(obj, spec.id_field)): obj for obj in spec.fetch(org, values)}

            for value in values:
                if obj := by_id.get(value):
                    results.append({"type": asset_type, spec.id_field: value, "name": spec.get_name(org, obj)})

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

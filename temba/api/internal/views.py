from rest_framework import status
from rest_framework.response import Response

from temba.notifications.models import Notification
from temba.utils import languages

from ..models import APIPermission, SSLPermission
from ..support import APISessionAuthentication, CreatedOnCursorPagination
from ..views import BaseAPIView, ListAPIMixin
from .serializers import ModelAsJsonSerializer


class BaseEndpoint(BaseAPIView):
    """
    Base class of all our internal API endpoints
    """

    authentication_classes = (APISessionAuthentication,)
    permission_classes = (SSLPermission, APIPermission)


# ============================================================
# Endpoints (A-Z)
# ============================================================


class LanguagesEndpoint(ListAPIMixin, BaseEndpoint):
    """
    Lists the flow languages for the current org.
    """

    permission = "orgs.org_read"

    def list(self, request, *args, **kwargs):
        def serialize(code: str) -> dict:
            return {
                "code": code,
                "name": languages.get_name(code),
                "iso": code,  # for backward compatibility
            }

        return Response(
            {"results": [serialize(c) for c in self.request.org.flow_languages]}, status=status.HTTP_200_OK
        )


class NotificationsEndpoint(ListAPIMixin, BaseEndpoint):
    """
    Lists the notifications for the current user in the current org.
    """

    permission = "notifications.notification_list"
    model = Notification
    pagination_class = CreatedOnCursorPagination
    serializer_class = ModelAsJsonSerializer

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(org=self.request.org, user=self.request.user)
            .prefetch_related("contact_import", "contact_export", "message_export", "results_export", "incident")
        )

"""
Endpoints called by the realtime messaging server that fronts browser WebSockets - server-to-server, never by
browsers directly.

Unlike the rest of the internal API (``/api/internal/``), which is called by the editor running in the user's
browser and so *must* be reachable from the public internet, every endpoint here is only ever called by the
realtime messaging server from inside our own network. That means this API can be made truly internal: serve
``/api/websockets/`` only on an internal-only network path (e.g. behind an internal load balancer) and refuse it
at the public edge, so it's never exposed to the internet at all. The shared-secret header enforced by
``HasWebSocketsSecret`` is defense-in-depth on top of that network isolation - it lets us reject anything that
isn't the realtime server even if the path is ever reachable - but the secret is not a substitute for keeping the
API off the public internet.
"""

from rest_framework.permissions import BasePermission
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.crypto import constant_time_compare

from temba.utils.uuid import is_uuid

from ..support import APISessionAuthentication


class WebSocketsSessionAuthentication(APISessionAuthentication):
    """
    Session auth for the server-to-server proxy calls. The realtime server forwards the browser's session cookie but
    can't present a CSRF token, so we no-op the CSRF check. Identity still comes from the real, signed session cookie.
    """

    def enforce_csrf(self, request):
        return


class HasWebSocketsSecret(BasePermission):
    """
    Gates the whole websockets API on a shared secret known only to the realtime server, compared in constant time
    against the ``WEBSOCKETS_AUTH_SECRET`` setting. The secret is required: a system check (see ``temba.api.checks``)
    catches a missing one at deploy time, and this fails closed at request time for the bare wsgi path where system
    checks don't run - so a misconfigured deployment can never silently accept any forwarded session cookie.
    """

    def has_permission(self, request, view):
        secret = settings.WEBSOCKETS_AUTH_SECRET
        if not secret:
            raise ImproperlyConfigured("WEBSOCKETS_AUTH_SECRET must be set to use the websockets API")

        return constant_time_compare(request.headers.get("X-Websockets-Secret", ""), secret)


class BaseEndpoint(APIView):
    """
    Base class for all websockets API endpoints.
    """

    authentication_classes = (WebSocketsSessionAuthentication,)
    permission_classes = (HasWebSocketsSecret,)
    renderer_classes = (JSONRenderer,)


class ConnectEndpoint(BaseEndpoint):
    """
    Connection proxy called by the realtime messaging server when a browser opens a WebSocket. The browser connects
    with no auth token; the realtime server forwards the browser's session cookie to us and we resolve the user,
    returning the connection result - the user identifier and the server-side channels to subscribe the connection to.

    Notifications are scoped to a user within a workspace, so the connection is subscribed to a single channel for the
    user's current workspace, ``notifications:<org-uuid>:<user-uuid>``; the ``notifications`` namespace is configured
    on the realtime server. A user with no current workspace gets no channels. If there's no authenticated session we
    return a disconnect instruction instead so the realtime server closes the connection.
    """

    def post(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return Response({"disconnect": {"code": 4401, "reason": "unauthorized"}})

        channels = []
        if request.org:
            channels.append(f"notifications:{request.org.uuid}:{user.uuid}")

        return Response({"result": {"user": str(user.uuid), "channels": channels}})


class SubscribeEndpoint(BaseEndpoint):
    """
    Subscribe proxy called by the realtime messaging server when a browser asks to subscribe to a channel that needs
    authorization (a namespace configured with a subscribe proxy on the realtime server). We resolve the user and their
    current workspace from the forwarded session cookie and allow the subscription only if it's one we recognize and
    the user has access to it in that workspace - everything else is denied.

    The only client-subscribable channel for now is a contact's chat history, ``chat:<contact-uuid>``, allowed only
    when the contact belongs to the user's current workspace. Access is always scoped to ``request.org``, so a channel
    for a contact in another workspace simply isn't found and is denied.
    """

    def post(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return Response({"disconnect": {"code": 4401, "reason": "unauthorized"}})

        if request.org and self.is_allowed(request, request.data.get("channel", "")):
            return Response({"result": {}})

        return Response({"error": {"code": 403, "message": "forbidden"}})

    def is_allowed(self, request, channel: str) -> bool:
        namespace, _, ref = channel.partition(":")

        if namespace == "chat":  # chat history for a contact in the current workspace
            return is_uuid(ref) and request.org.contacts.filter(uuid=ref, is_active=True).exists()

        return False

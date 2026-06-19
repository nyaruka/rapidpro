"""
Endpoints called by the realtime messaging server that fronts browser WebSockets - server-to-server, never by
browsers directly.

These handle connection authentication and lifecycle: ``connect`` authenticates a new connection from the forwarded
session cookie, and ``refresh`` periodically re-validates it. The connect result also attaches the user's identity to
the connection's server-side ``meta``, so the proxies that authorize individual channel subscriptions (handled by
another internal service) can act on that identity without re-reading the Django session.

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
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from ..support import APISessionAuthentication

# how long (seconds) a connection stays valid before the realtime server must re-validate it via the refresh proxy
CONNECTION_TTL = 5 * 60


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
    against the ``WEBSOCKETS_AUTH_SECRET`` setting. The secret is required and enforced by a system check (see
    ``temba.api.checks``) which fails the deploy if it's unset - and since system checks run as part of migrate /
    runserver, the secret is always configured by the time the API serves a request.
    """

    def has_permission(self, request, view):
        return constant_time_compare(request.headers.get("X-Websockets-Secret", ""), settings.WEBSOCKETS_AUTH_SECRET)


class BaseEndpoint(APIView):
    """
    Base class for all websockets API endpoints.
    """

    authentication_classes = (WebSocketsSessionAuthentication,)
    permission_classes = (HasWebSocketsSecret,)
    renderer_classes = (JSONRenderer,)

    def expire_at(self) -> int:
        """Unix time at which the connection should next be re-validated by the refresh proxy."""
        return int(timezone.now().timestamp()) + CONNECTION_TTL


class ConnectEndpoint(BaseEndpoint):
    """
    Connection proxy called by the realtime messaging server when a browser opens a WebSocket. The browser connects
    with no auth token; the realtime server forwards the browser's session cookie and we resolve the user.

    We currently require an authenticated user with a current workspace; if either is missing we return a disconnect
    instruction so the realtime server closes the connection.

    On success the result carries:
      * ``user`` - the user identifier (uuid);
      * ``channels`` - the server-side channels to subscribe the connection to: a single
        ``notifications:<org-uuid>:<user-uuid>`` for the user's current workspace;
      * ``meta`` - the user's identity (uuids and ids) attached to the connection so the subscription-authorization
        proxies can act on it without re-reading the session; ``meta`` is server-side only and never sent to the browser;
      * ``expire_at`` - when the realtime server should next call the refresh proxy to re-validate the connection.
    """

    def post(self, request, *args, **kwargs):
        user = request.user

        # for now a connection requires an authenticated user with a current workspace. This could be reworked in
        # future to also support anonymous connections - e.g. webchat - which have no Django user or workspace.
        if not user.is_authenticated or not request.org:
            return Response({"disconnect": {"code": 4401, "reason": "unauthorized"}})

        org = request.org
        meta = {"user_id": user.id, "user_uuid": str(user.uuid), "org_id": org.id, "org_uuid": str(org.uuid)}
        channels = [f"notifications:{org.uuid}:{user.uuid}"]

        return Response(
            {"result": {"user": str(user.uuid), "channels": channels, "meta": meta, "expire_at": self.expire_at()}}
        )


class RefreshEndpoint(BaseEndpoint):
    """
    Refresh proxy called periodically by the realtime messaging server before a connection's ``expire_at``. We re-check
    that the forwarded session is still valid (the user is still logged in) and either extend the connection with a new
    ``expire_at`` or let it expire - this is how a logout or session expiry eventually tears down the WebSocket.
    """

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({"result": {"expired": True}})

        return Response({"result": {"expire_at": self.expire_at()}})

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
from django.utils.crypto import constant_time_compare

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
    against the ``WEBSOCKETS_AUTH_SECRET`` setting. Only enforced when that setting is non-empty, so local development
    and tests work without it.
    """

    def has_permission(self, request, view):
        secret = getattr(settings, "WEBSOCKETS_AUTH_SECRET", None)
        if not secret:
            return True

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
    with no auth token; the realtime server forwards the browser's session cookie to us and we resolve the user plus
    their current workspace, returning the connection result - the user id and the server-side channels the connection
    should be subscribed to.

    Channels use integer DB ids (not UUIDs) because the services that publish to them key off the same ids; the
    ``user`` and ``org`` namespaces are configured on the realtime server. If there's no authenticated session we
    return a disconnect instruction instead so the realtime server closes the connection.
    """

    def post(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return Response({"disconnect": {"code": 4401, "reason": "unauthorized"}})

        channels = [f"user:{user.id}"]
        if request.org:
            channels.append(f"org:{request.org.id}")

        return Response({"result": {"user": str(user.id), "channels": channels}})

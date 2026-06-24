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

from django_valkey import get_valkey_connection
from rest_framework.permissions import BasePermission
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from temba.tickets.models import Ticket
from temba.utils.uuid import is_uuid

from ..support import APISessionAuthentication

# how long (seconds) a connection stays valid before the realtime server must re-validate it via the refresh proxy
CONNECTION_TTL = 5 * 60

# how long (seconds) a channel subscription stays authorized before the realtime server must re-check it via the
# sub_refresh proxy. A short window keeps the subscription index reasonably fresh without re-checking too often.
SUBSCRIPTION_WINDOW = 60

# how long (seconds) an entry lives in the valkey subscription index. Comfortably larger than SUBSCRIPTION_WINDOW so an
# entry survives until the next sub_refresh re-arms it; if refreshes stop (e.g. a dead connection that we never get an
# unsubscribe for) the entry simply ages out, which is how the index garbage-collects itself.
SUBSCRIPTION_TTL = 90


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
    that the connection is still valid - the user is still logged in and still has a current workspace, matching what
    ``connect`` requires - and either extend it with a new ``expire_at`` or let it expire. This is how a logout, session
    expiry, or losing access to the workspace eventually tears down the WebSocket.
    """

    def post(self, request, *args, **kwargs):
        # mirror connect: a connection is only kept alive while it has an authenticated user with a current workspace
        if not request.user.is_authenticated or not request.org:
            return Response({"result": {"expired": True}})

        return Response({"result": {"expire_at": self.expire_at()}})


class SubscriptionEndpoint(BaseEndpoint):
    """
    Base for the channel-subscription proxies (``subscribe`` and ``sub_refresh``). Both authorize a single
    client-requested channel against the live Django session - ``request.user`` and ``request.org`` - and, when
    allowed, record the subscription in a valkey index. The authorization deliberately reads the *current* workspace
    rather than anything carried on the connection, so access that has been revoked since connect stops working here.
    """

    def subscription_expire_at(self) -> int:
        """Unix time at which the realtime server should next re-check this subscription via the sub_refresh proxy."""
        return int(timezone.now().timestamp()) + SUBSCRIPTION_WINDOW

    def is_allowed(self, request, channel: str) -> bool:
        """
        Default-deny authorization of a client-requested channel for the current user's current workspace. Channels
        are namespaced (``<namespace>:<...>``); this dispatches on the namespace so adding a new channel type later is
        a one-method change. Callers must have already established an authenticated user with a current workspace.
        """
        if not isinstance(channel, str):  # malformed payload (e.g. a non-string channel) is just a denial, not a 500
            return False

        namespace, *parts = channel.split(":")

        if namespace == "history":
            return self._history_allowed(request.org, parts)

        return False

    def _history_allowed(self, org, parts: list) -> bool:
        """
        ``history:<contact-uuid>`` (a contact's history) or ``history:<contact-uuid>:<ticket-uuid>`` (a ticket's
        history). The contact must belong to the workspace and be active; for the ticket form the ticket must in turn
        belong to that contact - and so to the same workspace, since a ticket always shares its contact's org. Every
        segment is validated as a uuid before it reaches a query, since the uuid columns are ``UUIDField`` and would
        raise on a malformed value.
        """
        if not (1 <= len(parts) <= 2) or not all(is_uuid(p) for p in parts):
            return False

        contact = org.contacts.filter(uuid=parts[0], is_active=True).first()
        if not contact:
            return False

        if len(parts) == 1:
            return True

        return Ticket.objects.filter(uuid=parts[1], contact=contact).exists()

    def index_subscription(self, channel: str, client: str):
        """
        Record (or re-arm) a connection's subscription to a channel in the valkey index, so we can later answer
        "what/who is subscribed to channel X". The index is a sorted set per channel (key ``subs:<channel>``) whose
        members are connection ids scored by their expiry; the per-member score gives both lazy pruning and a fast read
        of who's currently subscribed. Centrifugo OSS has no unsubscribe/disconnect proxy, so the TTL plus periodic
        sub_refresh re-arming is the only reliable way to garbage-collect entries for connections that have gone away.
        """
        if not isinstance(client, str) or not client:  # nothing useful to index without a connection id
            return

        r = get_valkey_connection()
        now = int(timezone.now().timestamp())
        key = f"subs:{channel}"

        pipe = r.pipeline()
        pipe.zadd(key, {client: now + SUBSCRIPTION_TTL})
        pipe.zremrangebyscore(key, 0, now)  # lazily drop members that have already expired
        pipe.expire(key, SUBSCRIPTION_TTL)  # backstop so the key itself vanishes once nothing re-arms it
        pipe.execute()


class SubscribeEndpoint(SubscriptionEndpoint):
    """
    Subscribe proxy called by the realtime messaging server when a browser asks to subscribe to a channel. The request
    body carries the connection's ``client`` id and the requested ``channel``; we authorize that channel against the
    live session.

    An unauthenticated request is told to disconnect (its connection should never have got this far). Otherwise, if the
    user has a current workspace and may access the channel, we record the subscription and return an ``expire_at`` so
    the realtime server schedules a sub_refresh; anything else is refused with a forbidden error, which Centrifugo
    surfaces to the browser as a failed subscribe without tearing down the whole connection.
    """

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({"disconnect": {"code": 4401, "reason": "unauthorized"}})

        channel = request.data.get("channel", "")
        client = request.data.get("client", "")

        if request.org and self.is_allowed(request, channel):
            self.index_subscription(channel, client)
            return Response({"result": {"expire_at": self.subscription_expire_at()}})

        return Response({"error": {"code": 403, "message": "forbidden"}})


class SubRefreshEndpoint(SubscriptionEndpoint):
    """
    Sub refresh proxy called periodically by the realtime messaging server before a subscription's ``expire_at``. We
    re-run the same authorization as subscribe (access may have been revoked since), and either re-arm the index entry
    and return a fresh ``expire_at`` or let the subscription expire. Only the ``result`` is acted on for refreshes, so
    every not-allowed case - including a session that's gone - is reported as expired rather than as a disconnect.
    """

    def post(self, request, *args, **kwargs):
        channel = request.data.get("channel", "")
        client = request.data.get("client", "")

        if request.user.is_authenticated and request.org and self.is_allowed(request, channel):
            self.index_subscription(channel, client)
            return Response({"result": {"expire_at": self.subscription_expire_at()}})

        return Response({"result": {"expired": True}})

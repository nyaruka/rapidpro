from datetime import datetime, timezone as tzone
from unittest.mock import patch

from django_valkey import get_valkey_connection

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from temba.api.checks import websockets_auth_secret
from temba.api.tests.mixins import APITestMixin
from temba.api.websockets.views import SUBSCRIPTION_TTL, SUBSCRIPTION_WINDOW
from temba.tests import TembaTest
from temba.utils.uuid import uuid4

SECRET = "topsecret"


@override_settings(WEBSOCKETS_AUTH_SECRET=SECRET)
class EndpointsTest(APITestMixin, TembaTest):
    def post(self, name, data=None, *, client=None, secret=SECRET):
        headers = {"HTTP_X_WEBSOCKETS_SECRET": secret} if secret is not None else {}
        return (client or self.client).post(reverse(name), data or {}, content_type="application/json", **headers)

    def assertExpiry(self, expire_at):
        self.assertIsInstance(expire_at, int)
        self.assertGreater(expire_at, int(timezone.now().timestamp()))

    def assertConnect(self, response, *, user, channels, meta):
        self.assertEqual(200, response.status_code)
        result = response.json()["result"]
        self.assertExpiry(result.pop("expire_at"))
        self.assertEqual({"user": str(user.uuid), "channels": channels, "meta": meta}, result)

    def test_connect(self):
        endpoint_url = reverse("api.websockets.connect")

        # GET isn't supported - this endpoint only answers the realtime server's connect POST
        self.login(self.admin)
        self.assertEqual(405, self.client.get(endpoint_url, HTTP_X_WEBSOCKETS_SECRET=SECRET).status_code)

        # an authenticated user is subscribed to their notifications channel for their current workspace (scoped by
        # both org uuid and user uuid), and their identity is attached to the connection meta
        self.login(self.admin)
        self.assertConnect(
            self.post("api.websockets.connect"),
            user=self.admin,
            channels=[f"notifications:{self.org.uuid}:{self.admin.uuid}"],
            meta={
                "user_id": self.admin.id,
                "user_uuid": str(self.admin.uuid),
                "org_id": self.org.id,
                "org_uuid": str(self.org.uuid),
            },
        )

        # scoped per (org, user) - a different user in a different workspace gets their own channel and meta
        self.login(self.admin2, choose_org=self.org2)
        self.assertConnect(
            self.post("api.websockets.connect"),
            user=self.admin2,
            channels=[f"notifications:{self.org2.uuid}:{self.admin2.uuid}"],
            meta={
                "user_id": self.admin2.id,
                "user_uuid": str(self.admin2.uuid),
                "org_id": self.org2.id,
                "org_uuid": str(self.org2.uuid),
            },
        )

        # a user with no current workspace can't connect for now - they're told to disconnect
        self.login(self.admin)
        session = self.client.session
        del session["org_id"]
        session.save()
        response = self.post("api.websockets.connect")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"disconnect": {"code": 4401, "reason": "unauthorized"}}, response.json())

        # an unauthenticated request is told to disconnect
        self.client.logout()
        response = self.post("api.websockets.connect")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"disconnect": {"code": 4401, "reason": "unauthorized"}}, response.json())

        # because it's a server-to-server POST with no CSRF token, it still works when CSRF checks are enforced
        csrf_client = self.client_class(enforce_csrf_checks=True)
        csrf_client.login(username=self.admin.email, password=self.default_password)
        session = csrf_client.session
        session["org_id"] = self.org.id
        session.save()
        self.assertConnect(
            self.post("api.websockets.connect", client=csrf_client),
            user=self.admin,
            channels=[f"notifications:{self.org.uuid}:{self.admin.uuid}"],
            meta={
                "user_id": self.admin.id,
                "user_uuid": str(self.admin.uuid),
                "org_id": self.org.id,
                "org_uuid": str(self.org.uuid),
            },
        )

    def test_refresh(self):
        # a still-authenticated connection with a current workspace is extended with a new expiry
        self.login(self.admin)
        response = self.post("api.websockets.refresh")
        self.assertEqual(200, response.status_code)
        self.assertExpiry(response.json()["result"]["expire_at"])

        # losing the current workspace expires the connection (matches connect requiring one)
        session = self.client.session
        del session["org_id"]
        session.save()
        response = self.post("api.websockets.refresh")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"result": {"expired": True}}, response.json())

        # a connection whose session is gone is told it has expired, which tears the connection down
        self.client.logout()
        response = self.post("api.websockets.refresh")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"result": {"expired": True}}, response.json())

    def test_subscribe(self):
        contact = self.create_contact("Ann", phone="+1234", org=self.org)
        ticket = self.create_ticket(contact)

        # a second contact + ticket in the same workspace, to prove a ticket must belong to the named contact
        contact2 = self.create_contact("Cat", phone="+1236", org=self.org)
        ticket2 = self.create_ticket(contact2)

        # a contact + ticket in another workspace
        other = self.create_contact("Bob", phone="+1235", org=self.org2)
        other_ticket = self.create_ticket(other)

        def subscribe(channel, client="conn-1"):
            return self.post("api.websockets.subscribe", {"channel": channel, "client": client})

        self.login(self.admin)

        # allowed: a contact's history in the current workspace
        response = subscribe(f"history:{contact.uuid}")
        self.assertEqual(200, response.status_code)
        self.assertExpiry(response.json()["result"]["expire_at"])

        # allowed: a ticket's history for that contact
        response = subscribe(f"history:{contact.uuid}:{ticket.uuid}")
        self.assertEqual(200, response.status_code)
        self.assertExpiry(response.json()["result"]["expire_at"])

        def assertForbidden(channel):
            response = subscribe(channel)
            self.assertEqual(200, response.status_code)
            self.assertEqual({"error": {"code": 403, "message": "forbidden"}}, response.json())

        assertForbidden(f"history:{other.uuid}")  # contact in another workspace
        assertForbidden(f"history:{uuid4()}")  # contact not found
        assertForbidden(f"history:{contact.uuid}:{uuid4()}")  # ticket not found for the contact
        assertForbidden(f"history:{contact.uuid}:{ticket2.uuid}")  # ticket belongs to a different contact, same org
        assertForbidden(f"history:{contact.uuid}:{other_ticket.uuid}")  # ticket in another workspace
        assertForbidden(f"history:{other.uuid}:{other_ticket.uuid}")  # both in another workspace
        assertForbidden({"not": "a string"})  # non-string channel is a clean deny, not a 500
        assertForbidden("history:not-a-uuid")  # malformed contact uuid
        assertForbidden(f"history:{contact.uuid}:not-a-uuid")  # malformed ticket uuid
        assertForbidden(f"history:{contact.uuid}:{ticket.uuid}:extra")  # too many segments
        assertForbidden("history")  # too few segments
        assertForbidden(f"presence:{contact.uuid}")  # unknown namespace
        assertForbidden(
            f"notifications:{self.org.uuid}:{self.admin.uuid}"
        )  # server-side namespace, never via this proxy

        # an inactive contact is denied
        contact.is_active = False
        contact.save(update_fields=("is_active",))
        assertForbidden(f"history:{contact.uuid}")
        contact.is_active = True
        contact.save(update_fields=("is_active",))

        # a user with no current workspace is forbidden
        session = self.client.session
        del session["org_id"]
        session.save()
        assertForbidden(f"history:{contact.uuid}")

        # an unauthenticated request is told to disconnect
        self.client.logout()
        response = subscribe(f"history:{contact.uuid}")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"disconnect": {"code": 4401, "reason": "unauthorized"}}, response.json())

    def test_sub_refresh(self):
        contact = self.create_contact("Ann", phone="+1234", org=self.org)
        channel = f"history:{contact.uuid}"

        def sub_refresh(ch=channel, client="conn-1"):
            return self.post("api.websockets.sub_refresh", {"channel": ch, "client": client})

        # still authorized -> the subscription is extended
        self.login(self.admin)
        response = sub_refresh()
        self.assertEqual(200, response.status_code)
        self.assertExpiry(response.json()["result"]["expire_at"])

        # a channel the user may no longer access -> let the subscription expire
        response = sub_refresh(f"history:{uuid4()}")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"result": {"expired": True}}, response.json())

        # access revoked since subscribe (contact deactivated) -> expired
        contact.is_active = False
        contact.save(update_fields=("is_active",))
        response = sub_refresh()
        self.assertEqual(200, response.status_code)
        self.assertEqual({"result": {"expired": True}}, response.json())
        contact.is_active = True
        contact.save(update_fields=("is_active",))

        # losing the current workspace -> expired
        session = self.client.session
        del session["org_id"]
        session.save()
        response = sub_refresh()
        self.assertEqual(200, response.status_code)
        self.assertEqual({"result": {"expired": True}}, response.json())

        # no session at all -> expired (sub_refresh never disconnects)
        self.client.logout()
        response = sub_refresh()
        self.assertEqual(200, response.status_code)
        self.assertEqual({"result": {"expired": True}}, response.json())

    def test_subscription_index(self):
        contact = self.create_contact("Ann", phone="+1234", org=self.org)
        channel = f"history:{contact.uuid}"
        key = f"subs:{channel}"

        r = get_valkey_connection()
        r.delete(key)

        self.login(self.admin)

        # subscribe records the connection in the per-channel sorted set, scored by its expiry
        t0 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=tzone.utc)
        with patch("django.utils.timezone.now", return_value=t0):
            response = self.post("api.websockets.subscribe", {"channel": channel, "client": "conn-1"})
        self.assertEqual(200, response.status_code)
        self.assertEqual(int(t0.timestamp()) + SUBSCRIPTION_WINDOW, response.json()["result"]["expire_at"])
        self.assertEqual([b"conn-1"], r.zrange(key, 0, -1))
        score0 = r.zscore(key, "conn-1")
        self.assertEqual(int(t0.timestamp()) + SUBSCRIPTION_TTL, int(score0))

        # the key has a TTL backstop so a channel nothing re-arms eventually vanishes
        self.assertGreater(r.ttl(key), 0)
        self.assertLessEqual(r.ttl(key), SUBSCRIPTION_TTL)

        # an already-expired member from a dead connection
        r.zadd(key, {"dead-conn": int(t0.timestamp()) - 1})

        # sub_refresh later re-arms the entry with a later expiry and lazily prunes the dead one
        t1 = datetime(2024, 1, 1, 12, 0, 30, tzinfo=tzone.utc)
        with patch("django.utils.timezone.now", return_value=t1):
            response = self.post("api.websockets.sub_refresh", {"channel": channel, "client": "conn-1"})
        self.assertEqual(200, response.status_code)
        self.assertEqual(int(t1.timestamp()) + SUBSCRIPTION_WINDOW, response.json()["result"]["expire_at"])

        score1 = r.zscore(key, "conn-1")
        self.assertEqual(int(t1.timestamp()) + SUBSCRIPTION_TTL, int(score1))
        self.assertGreater(score1, score0)
        self.assertEqual([b"conn-1"], r.zrange(key, 0, -1))  # dead-conn was pruned

        # a second connection to the same channel coexists - the set tracks every subscriber, not just the latest
        with patch("django.utils.timezone.now", return_value=t1):
            response = self.post("api.websockets.subscribe", {"channel": channel, "client": "conn-2"})
        self.assertEqual(200, response.status_code)
        self.assertEqual({b"conn-1", b"conn-2"}, set(r.zrange(key, 0, -1)))

        # an empty connection id isn't indexed (no blank member added)
        response = self.post("api.websockets.subscribe", {"channel": channel, "client": ""})
        self.assertEqual(200, response.status_code)
        self.assertEqual({b"conn-1", b"conn-2"}, set(r.zrange(key, 0, -1)))

    def test_secret(self):
        self.login(self.admin)

        # a wrong secret is rejected for the whole API, even for an authenticated user
        self.assertEqual(403, self.post("api.websockets.connect", secret="open").status_code)

        # a missing secret is rejected
        self.assertEqual(403, self.post("api.websockets.connect", secret=None).status_code)

        # a correct secret doesn't bypass session auth - a browser with no session is still told to disconnect
        self.client.logout()
        response = self.post("api.websockets.connect")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"disconnect": {"code": 4401, "reason": "unauthorized"}}, response.json())

    @override_settings(WEBSOCKETS_AUTH_SECRET=None)
    def test_secret_required(self):
        # the secret is required, enforced by a deploy-time system check (system checks run as part of migrate /
        # runserver, so an unset secret fails the deploy before the API ever serves a request)
        errors = websockets_auth_secret(None)
        self.assertEqual(1, len(errors))
        self.assertEqual("WEBSOCKETS_AUTH_SECRET is not set.", errors[0].msg)

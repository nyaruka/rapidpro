from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from temba.api.checks import websockets_auth_secret
from temba.api.tests.mixins import APITestMixin
from temba.tests import TembaTest

SECRET = "topsecret"


@override_settings(WEBSOCKETS_AUTH_SECRET=SECRET)
class EndpointsTest(APITestMixin, TembaTest):
    def post(self, name, *, client=None, secret=SECRET):
        headers = {"HTTP_X_WEBSOCKETS_SECRET": secret} if secret is not None else {}
        return (client or self.client).post(reverse(name), {}, content_type="application/json", **headers)

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

        # a user with no current workspace gets no channels and no org in their meta
        self.login(self.admin)
        session = self.client.session
        del session["org_id"]
        session.save()
        self.assertConnect(
            self.post("api.websockets.connect"),
            user=self.admin,
            channels=[],
            meta={"user_id": self.admin.id, "user_uuid": str(self.admin.uuid)},
        )

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
        # a still-authenticated connection is extended with a new expiry
        self.login(self.admin)
        response = self.post("api.websockets.refresh")
        self.assertEqual(200, response.status_code)
        self.assertExpiry(response.json()["result"]["expire_at"])

        # a connection whose session is gone is told it has expired, which tears the connection down
        self.client.logout()
        response = self.post("api.websockets.refresh")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"result": {"expired": True}}, response.json())

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
        # the system check flags a deployment that hasn't configured the secret
        errors = websockets_auth_secret(None)
        self.assertEqual(1, len(errors))
        self.assertEqual("WEBSOCKETS_AUTH_SECRET is not set.", errors[0].msg)

        # and the API fails closed at request time for the bare wsgi path where system checks don't run
        self.login(self.admin)
        with self.assertRaises(ImproperlyConfigured):
            self.post("api.websockets.connect")

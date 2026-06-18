from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.urls import reverse

from temba.api.checks import websockets_auth_secret
from temba.api.tests.mixins import APITestMixin
from temba.tests import TembaTest
from temba.utils.uuid import uuid4

SECRET = "topsecret"

FORBIDDEN = {"error": {"code": 403, "message": "forbidden"}}


@override_settings(WEBSOCKETS_AUTH_SECRET=SECRET)
class EndpointsTest(APITestMixin, TembaTest):
    def post(self, *, client=None, secret=SECRET):
        headers = {"HTTP_X_WEBSOCKETS_SECRET": secret} if secret is not None else {}
        return (client or self.client).post(
            reverse("api.websockets.connect"), {}, content_type="application/json", **headers
        )

    def subscribe(self, channel: str):
        return self.client.post(
            reverse("api.websockets.subscribe"),
            {"channel": channel},
            content_type="application/json",
            HTTP_X_WEBSOCKETS_SECRET=SECRET,
        )

    def test_connect(self):
        endpoint_url = reverse("api.websockets.connect")

        # GET isn't supported - this endpoint only answers the realtime server's connect POST
        self.login(self.admin)
        self.assertEqual(405, self.client.get(endpoint_url, HTTP_X_WEBSOCKETS_SECRET=SECRET).status_code)

        # an authenticated user is subscribed to their notifications channel for their current workspace, scoped by
        # both org uuid and user uuid
        self.login(self.admin)
        response = self.post()
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "result": {
                    "user": str(self.admin.uuid),
                    "channels": [f"notifications:{self.org.uuid}:{self.admin.uuid}"],
                }
            },
            response.json(),
        )

        # the channel is scoped per (org, user) - a different user in a different workspace gets their own channel
        self.login(self.admin2, choose_org=self.org2)
        response = self.post()
        self.assertEqual(
            {
                "result": {
                    "user": str(self.admin2.uuid),
                    "channels": [f"notifications:{self.org2.uuid}:{self.admin2.uuid}"],
                }
            },
            response.json(),
        )

        # a user with no current workspace gets no channels
        self.login(self.admin)
        session = self.client.session
        del session["org_id"]
        session.save()
        response = self.post()
        self.assertEqual({"result": {"user": str(self.admin.uuid), "channels": []}}, response.json())

        # an unauthenticated request is told to disconnect
        self.client.logout()
        response = self.post()
        self.assertEqual(200, response.status_code)
        self.assertEqual({"disconnect": {"code": 4401, "reason": "unauthorized"}}, response.json())

        # because it's a server-to-server POST with no CSRF token, it still works when CSRF checks are enforced
        csrf_client = self.client_class(enforce_csrf_checks=True)
        csrf_client.login(username=self.admin.email, password=self.default_password)
        session = csrf_client.session
        session["org_id"] = self.org.id
        session.save()
        response = self.post(client=csrf_client)
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "result": {
                    "user": str(self.admin.uuid),
                    "channels": [f"notifications:{self.org.uuid}:{self.admin.uuid}"],
                }
            },
            response.json(),
        )

    def test_subscribe(self):
        contact = self.create_contact("Ann", phone="+1234567001")
        other_org_contact = self.create_contact("Bob", phone="+1234567002", org=self.org2)

        # an unauthenticated request is told to disconnect
        response = self.subscribe(f"chat:{contact.uuid}")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"disconnect": {"code": 4401, "reason": "unauthorized"}}, response.json())

        self.login(self.admin)

        # a contact in the user's current workspace is allowed
        response = self.subscribe(f"chat:{contact.uuid}")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"result": {}}, response.json())

        # a contact in another workspace is denied (not found when scoped to the current org)
        self.assertEqual(FORBIDDEN, self.subscribe(f"chat:{other_org_contact.uuid}").json())

        # a non-existent contact is denied
        self.assertEqual(FORBIDDEN, self.subscribe(f"chat:{uuid4()}").json())

        # a malformed contact uuid is denied (and doesn't error)
        self.assertEqual(FORBIDDEN, self.subscribe("chat:not-a-uuid").json())

        # an unrecognized namespace is denied (default deny)
        self.assertEqual(FORBIDDEN, self.subscribe(f"secrets:{contact.uuid}").json())

        # a released contact is denied
        contact.is_active = False
        contact.save(update_fields=("is_active",))
        self.assertEqual(FORBIDDEN, self.subscribe(f"chat:{contact.uuid}").json())
        contact.is_active = True
        contact.save(update_fields=("is_active",))

        # a user with no current workspace is denied
        session = self.client.session
        del session["org_id"]
        session.save()
        self.assertEqual(FORBIDDEN, self.subscribe(f"chat:{contact.uuid}").json())

    def test_secret(self):
        self.login(self.admin)

        # a wrong secret is rejected for the whole API, even for an authenticated user
        self.assertEqual(403, self.post(secret="open").status_code)

        # a missing secret is rejected
        self.assertEqual(403, self.post(secret=None).status_code)

        # a correct secret doesn't bypass session auth - a browser with no session is still told to disconnect
        self.client.logout()
        response = self.post()
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
            self.post()

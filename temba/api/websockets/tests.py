from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.urls import reverse

from temba.api.checks import websockets_auth_secret
from temba.api.tests.mixins import APITestMixin
from temba.tests import TembaTest

SECRET = "topsecret"


@override_settings(WEBSOCKETS_AUTH_SECRET=SECRET)
class EndpointsTest(APITestMixin, TembaTest):
    def post(self, *, client=None, secret=SECRET):
        headers = {"HTTP_X_WEBSOCKETS_SECRET": secret} if secret is not None else {}
        return (client or self.client).post(
            reverse("api.websockets.connect"), {}, content_type="application/json", **headers
        )

    def test_connect(self):
        endpoint_url = reverse("api.websockets.connect")

        # GET isn't supported - this endpoint only answers the realtime server's connect POST
        self.login(self.admin)
        self.assertEqual(405, self.client.get(endpoint_url, HTTP_X_WEBSOCKETS_SECRET=SECRET).status_code)

        # an authenticated user is subscribed to their own notifications channel, keyed by user uuid
        self.login(self.admin)
        response = self.post()
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {"result": {"user": str(self.admin.uuid), "channels": [f"notifications:{self.admin.uuid}"]}},
            response.json(),
        )

        # the channel is per-user - a different user gets their own notifications channel (not workspace-scoped)
        self.login(self.editor)
        response = self.post()
        self.assertEqual(
            {"result": {"user": str(self.editor.uuid), "channels": [f"notifications:{self.editor.uuid}"]}},
            response.json(),
        )

        # an unauthenticated request is told to disconnect
        self.client.logout()
        response = self.post()
        self.assertEqual(200, response.status_code)
        self.assertEqual({"disconnect": {"code": 4401, "reason": "unauthorized"}}, response.json())

        # because it's a server-to-server POST with no CSRF token, it still works when CSRF checks are enforced
        csrf_client = self.client_class(enforce_csrf_checks=True)
        csrf_client.login(username=self.admin.email, password=self.default_password)
        response = self.post(client=csrf_client)
        self.assertEqual(200, response.status_code)
        self.assertEqual(str(self.admin.uuid), response.json()["result"]["user"])

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

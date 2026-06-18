from django.test import override_settings
from django.urls import reverse

from temba.api.tests.mixins import APITestMixin
from temba.tests import TembaTest


class EndpointsTest(APITestMixin, TembaTest):
    def test_connect(self):
        endpoint_url = reverse("api.websockets.connect")

        def post(client=None):
            return (client or self.client).post(endpoint_url, {}, content_type="application/json")

        # GET isn't supported - this endpoint only answers the realtime server's connect POST
        self.login(self.admin)
        self.assertEqual(405, self.client.get(endpoint_url).status_code)

        # an authenticated user gets subscribed to their own channel plus their current workspace's channel
        self.login(self.admin)
        response = post()
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {"result": {"user": str(self.admin.id), "channels": [f"user:{self.admin.id}", f"org:{self.org.id}"]}},
            response.json(),
        )

        # the workspace channel is scoped to the current org - a user on a different workspace gets that org's channel
        self.login(self.admin2, choose_org=self.org2)
        response = post()
        self.assertEqual(
            {"result": {"user": str(self.admin2.id), "channels": [f"user:{self.admin2.id}", f"org:{self.org2.id}"]}},
            response.json(),
        )

        # with no current workspace, only the user channel is returned
        self.login(self.admin)
        session = self.client.session
        del session["org_id"]
        session.save()
        response = post()
        self.assertEqual(
            {"result": {"user": str(self.admin.id), "channels": [f"user:{self.admin.id}"]}}, response.json()
        )

        # an unauthenticated request is told to disconnect
        self.client.logout()
        response = post()
        self.assertEqual(200, response.status_code)
        self.assertEqual({"disconnect": {"code": 4401, "reason": "unauthorized"}}, response.json())

        # because it's a server-to-server POST with no CSRF token, it still works when CSRF checks are enforced
        csrf_client = self.client_class(enforce_csrf_checks=True)
        csrf_client.login(username=self.admin.email, password=self.default_password)
        session = csrf_client.session
        session["org_id"] = self.org.id
        session.save()
        response = post(csrf_client)
        self.assertEqual(200, response.status_code)
        self.assertEqual(str(self.admin.id), response.json()["result"]["user"])

    @override_settings(WEBSOCKETS_AUTH_SECRET="sesame")
    def test_connect_with_secret(self):
        endpoint_url = reverse("api.websockets.connect")
        self.login(self.admin)

        # the correct shared secret is accepted
        response = self.client.post(
            endpoint_url, {}, content_type="application/json", HTTP_X_WEBSOCKETS_SECRET="sesame"
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(str(self.admin.id), response.json()["result"]["user"])

        # a wrong secret is rejected for the whole API, even for an authenticated user
        response = self.client.post(endpoint_url, {}, content_type="application/json", HTTP_X_WEBSOCKETS_SECRET="open")
        self.assertEqual(403, response.status_code)

        # a missing secret is rejected
        response = self.client.post(endpoint_url, {}, content_type="application/json")
        self.assertEqual(403, response.status_code)

        # a correct secret doesn't bypass session auth - a browser with no session is still told to disconnect
        self.client.logout()
        response = self.client.post(
            endpoint_url, {}, content_type="application/json", HTTP_X_WEBSOCKETS_SECRET="sesame"
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual({"disconnect": {"code": 4401, "reason": "unauthorized"}}, response.json())

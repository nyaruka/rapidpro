from unittest.mock import patch

from django.urls import reverse

from temba.tests import CRUDLTestMixin, MockResponse, TembaTest
from temba.utils import json

from ...models import Channel
from .type import ViberType
from .views import CONFIG_WELCOME_MESSAGE


class ViberTypeTest(TembaTest, CRUDLTestMixin):
    def setUp(self):
        super().setUp()

        with patch("requests.post") as mock_post:
            mock_post.return_value = (
                MockResponse(
                    200, json.dumps({"status": 0, "status_message": "ok", "id": "viberId", "uri": "viberName"})
                ),
            )
            self.channel = Channel.create(
                self.org,
                self.admin,
                None,
                "VP",
                name="Viber",
                address="12345",
                role="SR",
                schemes=["viber"],
                config={"auth_token": "abcd1234"},
            )

    @patch("requests.post")
    def test_claim(self, mock_post):
        url = reverse("channels.types.viber.claim")

        self.login(self.admin)

        # check that claim page URL appears on claim list page
        response = self.client.get(reverse("channels.channel_claim"))
        self.assertContains(response, url)

        # try submitting with invalid token
        mock_post.return_value = MockResponse(400, json.dumps({"status": 3, "status_message": "Invalid token"}))
        response = self.client.post(url, {"auth_token": "invalid"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Error validating authentication token")

        # ok this time claim with a success
        mock_post.side_effect = [
            MockResponse(200, json.dumps({"status": 0, "status_message": "ok", "id": "viberId", "uri": "viberName"})),
            MockResponse(200, json.dumps({"status": 0, "status_message": "ok", "id": "viberId", "uri": "viberName"})),
            MockResponse(200, json.dumps({"status": 0, "status_message": "ok"})),
        ]

        self.client.post(url, {"auth_token": "123456"}, follow=True)

        # assert our channel got created
        channel = Channel.objects.get(address="viberId")
        self.assertEqual(channel.config["auth_token"], "123456")
        self.assertEqual(channel.name, "viberName")

        # should have been called with our webhook URL
        self.assertEqual(mock_post.call_args[0][0], "https://chatapi.viber.com/pa/set_webhook")

    @patch("requests.post")
    def test_release(self, mock_post):
        mock_post.side_effect = [MockResponse(200, json.dumps({"status": 0, "status_message": "ok"}))]
        self.channel.release(self.admin, interrupt=False)

        self.assertEqual(mock_post.call_args[0][0], "https://chatapi.viber.com/pa/set_webhook")

    def test_update(self):
        update_url = reverse("channels.channel_update", args=[self.channel.id])
        read_url = reverse("channels.channel_read", args=[self.channel.uuid])

        self.assertRequestDisallowed(update_url, [None, self.agent, self.admin2])
        self.assertUpdateFetch(
            update_url,
            [self.editor, self.admin],
            form_fields={"name": "Viber", "is_enabled": True, "welcome_message": ""},
        )

        self.assertUpdateSubmit(
            update_url,
            self.admin,
            {"name": "Updated", "is_enabled": True, "welcome_message": "Welcome, please subscribe for more"},
        )

        self.channel.refresh_from_db()
        self.assertEqual("Updated", self.channel.name)
        self.assertEqual("Welcome, please subscribe for more", self.channel.config.get(CONFIG_WELCOME_MESSAGE))

        self.assertUpdateFetch(
            update_url,
            [self.editor, self.admin],
            form_fields={
                "name": "Updated",
                "is_enabled": True,
                "welcome_message": "Welcome, please subscribe for more",
            },
        )

        # read page has link to update page
        self.assertContentMenu(read_url, self.admin, ["Configuration", "Logs", "Edit", "Delete"])

        # staff users see extra log policy field
        self.assertUpdateFetch(
            update_url,
            [self.customer_support],
            form_fields=["name", "is_enabled", "log_policy", "welcome_message"],
            choose_org=self.org,
        )

    def test_get_error_ref_url(self):
        self.assertEqual(
            "https://developers.viber.com/docs/api/rest-bot-api/#error-codes",
            ViberType().get_error_ref_url(None, "12"),
        )

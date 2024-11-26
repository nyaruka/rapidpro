from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse

from temba.tests import MockResponse, TembaTest
from temba.triggers.models import Trigger
from temba.utils import json
from temba.utils.text import truncate

from ...models import Channel
from .type import FacebookAppType


class FacebookTypeTest(TembaTest):
    def setUp(self):
        super().setUp()

        self.channel = Channel.create(
            self.org,
            self.user,
            None,
            "FBA",
            name="Facebook",
            address="12345",
            role="SR",
            schemes=["facebook"],
            config={"auth_token": "09876543", "page_name": "FirstName"},
        )

    @override_settings(FACEBOOK_APPLICATION_ID="FB_APP_ID", FACEBOOK_APPLICATION_SECRET="FB_APP_SECRET")
    @patch("requests.post")
    @patch("requests.get")
    def test_claim(self, mock_get, mock_post):
        token = "x" * 200
        mock_get.side_effect = [
            MockResponse(200, json.dumps({"data": {"user_id": "098765", "expired_at": 100}})),
            MockResponse(200, json.dumps({"access_token": f"long-life-user-{token}"})),
            MockResponse(
                200,
                json.dumps({"data": [{"name": "Temba", "id": "123456", "access_token": f"page-long-life-{token}"}]}),
            ),
        ]

        mock_post.return_value = MockResponse(200, json.dumps({"success": True}))

        url = reverse("channels.types.facebookapp.claim")

        self.login(self.admin)

        # check that claim page URL appears on claim list page
        response = self.client.get(reverse("channels.channel_claim"))
        self.assertContains(response, url)

        # can fetch the claim page
        response = self.client.get(url)
        self.assertContains(response, "Connect Facebook")
        self.assertEqual(response.context["facebook_app_id"], "FB_APP_ID")
        self.assertEqual(response.context["claim_url"], url)

        post_data = response.context["form"].initial
        post_data["user_access_token"] = token
        post_data["page_id"] = "123456"
        post_data["page_name"] = "Temba"

        response = self.client.post(url, post_data, follow=True)

        # assert our channel got created
        channel = Channel.objects.get(address="123456", channel_type="FBA")
        self.assertEqual(channel.config[Channel.CONFIG_AUTH_TOKEN], f"page-long-life-{token}")
        self.assertEqual(channel.config[Channel.CONFIG_PAGE_NAME], "Temba")
        self.assertEqual(channel.address, "123456")

        self.assertEqual(response.request["PATH_INFO"], reverse("channels.channel_read", args=[channel.uuid]))

        mock_get.assert_any_call(
            "https://graph.facebook.com/v18.0/debug_token",
            params={"input_token": token, "access_token": "FB_APP_ID|FB_APP_SECRET"},
        )

        mock_get.assert_any_call(
            "https://graph.facebook.com/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": "FB_APP_ID",
                "client_secret": "FB_APP_SECRET",
                "fb_exchange_token": token,
            },
        )

        mock_get.assert_any_call(
            "https://graph.facebook.com/v18.0/098765/accounts", params={"access_token": f"long-life-user-{token}"}
        )

        mock_post.assert_any_call(
            "https://graph.facebook.com/v18.0/123456/subscribed_apps",
            data={
                "subscribed_fields": "messages,message_deliveries,messaging_optins,messaging_optouts,messaging_postbacks,message_reads,messaging_referrals,messaging_handovers"
            },
            params={"access_token": f"page-long-life-{token}"},
        )

        mock_get.side_effect = [
            MockResponse(200, json.dumps({"data": {"user_id": "098765"}})),
            Exception("blah"),
        ]

        response = self.client.get(url)
        self.assertContains(response, "Connect Facebook")
        self.assertEqual(response.context["facebook_app_id"], "FB_APP_ID")
        self.assertEqual(response.context["claim_url"], url)

        post_data = response.context["form"].initial
        post_data["user_access_token"] = token
        post_data["page_id"] = "123456"
        post_data["page_name"] = "Temba"

        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(
            response.context["form"].errors["__all__"][0],
            "Sorry your Facebook channel could not be connected. Please try again",
        )

    @override_settings(FACEBOOK_APPLICATION_ID="FB_APP_ID", FACEBOOK_APPLICATION_SECRET="FB_APP_SECRET")
    @patch("requests.post")
    @patch("requests.get")
    def test_claim_long_name(self, mock_get, mock_post):
        token = "x" * 200
        long_name = "Temba" * 20

        truncated_name = truncate(long_name, 64)

        mock_get.side_effect = [
            MockResponse(200, json.dumps({"data": {"user_id": "098765", "expired_at": 100}})),
            MockResponse(200, json.dumps({"access_token": f"long-life-user-{token}"})),
            MockResponse(
                200,
                json.dumps({"data": [{"name": long_name, "id": "123456", "access_token": f"page-long-life-{token}"}]}),
            ),
        ]

        mock_post.return_value = MockResponse(200, json.dumps({"success": True}))

        url = reverse("channels.types.facebookapp.claim")

        self.login(self.admin)

        # check that claim page URL appears on claim list page
        response = self.client.get(reverse("channels.channel_claim"))
        self.assertContains(response, url)

        # can fetch the claim page
        response = self.client.get(url)
        self.assertContains(response, "Connect Facebook")
        self.assertEqual(response.context["facebook_app_id"], "FB_APP_ID")
        self.assertEqual(response.context["claim_url"], url)

        post_data = response.context["form"].initial
        post_data["user_access_token"] = token
        post_data["page_id"] = "123456"
        post_data["page_name"] = long_name

        response = self.client.post(url, post_data, follow=True)

        # assert our channel got created
        channel = Channel.objects.get(address="123456", channel_type="FBA")
        self.assertEqual(channel.config[Channel.CONFIG_AUTH_TOKEN], f"page-long-life-{token}")
        self.assertEqual(channel.config[Channel.CONFIG_PAGE_NAME], truncated_name)
        self.assertEqual(channel.address, "123456")

    @override_settings(FACEBOOK_APPLICATION_ID="FB_APP_ID", FACEBOOK_APPLICATION_SECRET="FB_APP_SECRET")
    @patch("requests.post")
    @patch("requests.get")
    def test_claim_already_connected(self, mock_get, mock_post):
        channel = Channel.objects.get(address="12345", channel_type="FBA")
        self.assertEqual(channel.config[Channel.CONFIG_AUTH_TOKEN], "09876543")
        self.assertEqual(channel.config[Channel.CONFIG_PAGE_NAME], "FirstName")
        self.assertEqual(channel.name, "Facebook")

        token = "x" * 200
        name = "Temba"

        mock_get.side_effect = [
            MockResponse(200, json.dumps({"data": {"user_id": "098765", "expired_at": 100}})),
            MockResponse(200, json.dumps({"access_token": f"long-life-user-{token}"})),
            MockResponse(
                200,
                json.dumps({"data": [{"name": name, "id": "12345", "access_token": f"page-long-life-update-{token}"}]}),
            ),
        ]

        mock_post.return_value = MockResponse(200, json.dumps({"success": True}))

        url = reverse("channels.types.facebookapp.claim")

        self.login(self.admin)

        # check that claim page URL appears on claim list page
        response = self.client.get(reverse("channels.channel_claim"))
        self.assertContains(response, url)

        # can fetch the claim page
        response = self.client.get(url)
        self.assertContains(response, "Connect Facebook")
        self.assertEqual(response.context["facebook_app_id"], "FB_APP_ID")
        self.assertEqual(response.context["claim_url"], url)

        post_data = response.context["form"].initial
        post_data["user_access_token"] = token
        post_data["page_id"] = "12345"
        post_data["page_name"] = name

        response = self.client.post(url, post_data, follow=True)
        channel = Channel.objects.get(address="12345", channel_type="FBA")
        self.assertEqual(channel.config[Channel.CONFIG_AUTH_TOKEN], f"page-long-life-update-{token}")
        self.assertEqual(channel.config[Channel.CONFIG_PAGE_NAME], "Temba")
        self.assertEqual(channel.name, "Facebook")

        mock_get.side_effect = [
            MockResponse(200, json.dumps({"data": {"user_id": "098765", "expired_at": 100}})),
            MockResponse(200, json.dumps({"access_token": f"long-life-user-{token}"})),
            MockResponse(
                200,
                json.dumps({"data": [{"name": name, "id": "12345", "access_token": f"page-long-life-{token}"}]}),
            ),
        ]

        self.login(self.admin2)

        # check that claim page URL appears on claim list page
        response = self.client.get(reverse("channels.channel_claim"))
        self.assertContains(response, url)

        # can fetch the claim page
        response = self.client.get(url)
        self.assertContains(response, "Connect Facebook")
        self.assertEqual(response.context["facebook_app_id"], "FB_APP_ID")
        self.assertEqual(response.context["claim_url"], url)

        post_data = response.context["form"].initial
        post_data["user_access_token"] = token
        post_data["page_id"] = "12345"
        post_data["page_name"] = name

        response = self.client.post(url, post_data, follow=True)
        self.assertContains(response, "This channel is already connected in another workspace.")

    @patch("requests.delete")
    def test_release(self, mock_delete):
        mock_delete.return_value = MockResponse(200, json.dumps({"success": True}))
        self.channel.release(self.admin)

        mock_delete.assert_called_once_with(
            "https://graph.facebook.com/v18.0/12345/subscribed_apps", params={"access_token": "09876543"}
        )

    def test_new_conversation_triggers(self):
        flow = self.create_flow("Test")

        with patch("requests.post") as mock_post:
            mock_post.return_value = MockResponse(200, json.dumps({"success": True}))

            trigger = Trigger.create(self.org, self.admin, Trigger.TYPE_NEW_CONVERSATION, flow, channel=self.channel)

            mock_post.assert_called_once_with(
                "https://graph.facebook.com/v18.0/me/messenger_profile",
                json={"get_started": {"payload": "get_started"}},
                headers={"Content-Type": "application/json"},
                params={"access_token": "09876543"},
            )
            mock_post.reset_mock()
            trigger.refresh_from_db()
            self.assertFalse(trigger.is_archived)

        with patch("requests.delete") as mock_post:
            mock_post.return_value = MockResponse(200, json.dumps({"success": True}))

            trigger.archive(self.admin)

            mock_post.assert_called_once_with(
                "https://graph.facebook.com/v18.0/me/messenger_profile",
                json={"fields": ["get_started"]},
                headers={"Content-Type": "application/json"},
                params={"access_token": "09876543"},
            )
            mock_post.reset_mock()
            trigger.refresh_from_db()
            self.assertTrue(trigger.is_archived)

        with patch("requests.post") as mock_post:
            mock_post.return_value = MockResponse(200, json.dumps({"success": True}))

            trigger.restore(self.admin)

            mock_post.assert_called_once_with(
                "https://graph.facebook.com/v18.0/me/messenger_profile",
                json={"get_started": {"payload": "get_started"}},
                headers={"Content-Type": "application/json"},
                params={"access_token": "09876543"},
            )
            mock_post.reset_mock()
            trigger.refresh_from_db()
            self.assertFalse(trigger.is_archived)

        with patch("requests.delete") as mock_post:
            mock_post.side_effect = [MockResponse(400, "Error found")]

            with self.assertRaises(Exception):
                trigger.archive(self.admin)

            mock_post.assert_called_once_with(
                "https://graph.facebook.com/v18.0/me/messenger_profile",
                json={"fields": ["get_started"]},
                headers={"Content-Type": "application/json"},
                params={"access_token": "09876543"},
            )
            mock_post.reset_mock()
            trigger.refresh_from_db()
            self.assertTrue(trigger.is_archived)

    def test_get_error_ref_url(self):
        self.assertEqual(
            "https://developers.facebook.com/docs/messenger-platform/error-codes",
            FacebookAppType().get_error_ref_url(None, "190"),
        )

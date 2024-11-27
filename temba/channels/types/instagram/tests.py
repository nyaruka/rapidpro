from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse

from temba.tests import MockResponse, TembaTest
from temba.utils import json
from temba.utils.text import truncate

from ...models import Channel
from .type import InstagramType


class InstagramTypeTest(TembaTest):
    def setUp(self):
        super().setUp()

        self.token = "x" * 200
        self.long_life_page_token = f"page-long-life-{self.token}"
        self.channel = Channel.create(
            self.org,
            self.user,
            None,
            "IG",
            name="Instagram",
            address="019283",
            role="SR",
            schemes=["instagram"],
            config={"auth_token": "09876543", "page_name": "FirstName", "page_id": "123456"},
        )

    @override_settings(FACEBOOK_APPLICATION_ID="FB_APP_ID", FACEBOOK_APPLICATION_SECRET="FB_APP_SECRET")
    @patch("requests.post")
    @patch("requests.get")
    def test_claim(self, mock_get, mock_post):
        mock_get.side_effect = [
            MockResponse(200, json.dumps({"data": {"user_id": "098765", "expired_at": 100}})),
            MockResponse(200, json.dumps({"access_token": f"long-life-user-{self.token}"})),
            MockResponse(
                200,
                json.dumps(
                    {
                        "data": [
                            {
                                "name": "Temba",
                                "id": "123456",
                                "access_token": self.long_life_page_token,
                            }
                        ]
                    }
                ),
            ),
            MockResponse(
                200,
                json.dumps({"instagram_business_account": {"id": "1234567"}, "id": "998776"}),
            ),
        ]

        mock_post.return_value = MockResponse(200, json.dumps({"success": True}))

        url = reverse("channels.types.instagram.claim")

        self.login(self.admin)

        # check that claim page URL appears on claim list page
        response = self.client.get(reverse("channels.channel_claim"))
        self.assertContains(response, url)

        # can fetch the claim page
        response = self.client.get(url)
        self.assertContains(response, "Connect Instagram")
        self.assertEqual(response.context["facebook_app_id"], "FB_APP_ID")
        self.assertEqual(response.context["claim_url"], url)

        post_data = response.context["form"].initial
        post_data["user_access_token"] = self.token
        post_data["page_id"] = "123456"
        post_data["page_name"] = "Temba"

        response = self.client.post(url, post_data, follow=True)

        # assert our channel got created
        channel = Channel.objects.get(address="1234567", channel_type="IG")  # address is ig user
        self.assertEqual(channel.config[Channel.CONFIG_AUTH_TOKEN], self.long_life_page_token)
        self.assertEqual(channel.config[Channel.CONFIG_PAGE_NAME], "Temba")
        self.assertEqual(channel.address, "1234567")

        self.assertEqual(
            response.request["PATH_INFO"],
            reverse("channels.channel_read", args=[channel.uuid]),
        )

        mock_get.assert_any_call(
            "https://graph.facebook.com/v18.0/debug_token",
            params={"input_token": self.token, "access_token": "FB_APP_ID|FB_APP_SECRET"},
        )

        mock_get.assert_any_call(
            "https://graph.facebook.com/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": "FB_APP_ID",
                "client_secret": "FB_APP_SECRET",
                "fb_exchange_token": self.token,
            },
        )

        mock_get.assert_any_call(
            "https://graph.facebook.com/v18.0/098765/accounts", params={"access_token": f"long-life-user-{self.token}"}
        )

        mock_post.assert_any_call(
            "https://graph.facebook.com/v18.0/123456/subscribed_apps",
            data={"subscribed_fields": "messages,messaging_postbacks"},
            params={"access_token": self.long_life_page_token},
        )

        mock_get.assert_any_call(
            "https://graph.facebook.com/123456?fields=instagram_business_account",
            params={
                "access_token": f"long-life-user-{self.token}",
            },
        )

        mock_get.side_effect = [
            MockResponse(200, json.dumps({"data": {"user_id": "098765"}})),
            Exception("blah"),
        ]

        response = self.client.get(url)
        self.assertContains(response, "Connect Instagram")
        self.assertEqual(response.context["facebook_app_id"], "FB_APP_ID")
        self.assertEqual(response.context["claim_url"], url)

        post_data = response.context["form"].initial
        post_data["user_access_token"] = self.token
        post_data["page_id"] = "123456"
        post_data["page_name"] = "Temba"

        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(
            response.context["form"].errors["__all__"][0],
            "Sorry your Instagram channel could not be connected. Please try again",
        )

    @override_settings(FACEBOOK_APPLICATION_ID="FB_APP_ID", FACEBOOK_APPLICATION_SECRET="FB_APP_SECRET")
    @patch("requests.post")
    @patch("requests.get")
    def test_claim_long_name(self, mock_get, mock_post):
        long_name = "Temba" * 20
        truncated_name = truncate(long_name, 64)

        mock_get.side_effect = [
            MockResponse(200, json.dumps({"data": {"user_id": "098765", "expired_at": 100}})),
            MockResponse(200, json.dumps({"access_token": f"long-life-user-{self.token}"})),
            MockResponse(
                200,
                json.dumps(
                    {
                        "data": [
                            {
                                "name": long_name,
                                "id": "123456",
                                "access_token": self.long_life_page_token,
                            }
                        ]
                    }
                ),
            ),
            MockResponse(
                200,
                json.dumps({"instagram_business_account": {"id": "1234567"}, "id": "998776"}),
            ),
        ]

        mock_post.return_value = MockResponse(200, json.dumps({"success": True}))

        url = reverse("channels.types.instagram.claim")

        self.login(self.admin)

        # check that claim page URL appears on claim list page
        response = self.client.get(reverse("channels.channel_claim"))
        self.assertContains(response, url)

        # can fetch the claim page
        response = self.client.get(url)
        self.assertContains(response, "Connect Instagram")
        self.assertEqual(response.context["facebook_app_id"], "FB_APP_ID")
        self.assertEqual(response.context["claim_url"], url)

        post_data = response.context["form"].initial
        post_data["user_access_token"] = self.token
        post_data["page_id"] = "123456"
        post_data["page_name"] = long_name

        response = self.client.post(url, post_data, follow=True)

        # assert our channel got created
        channel = Channel.objects.get(address="1234567", channel_type="IG")  # address is ig user
        self.assertEqual(channel.config[Channel.CONFIG_AUTH_TOKEN], self.long_life_page_token)
        self.assertEqual(channel.config[Channel.CONFIG_PAGE_NAME], truncated_name)
        self.assertEqual(channel.address, "1234567")

    @override_settings(FACEBOOK_APPLICATION_ID="FB_APP_ID", FACEBOOK_APPLICATION_SECRET="FB_APP_SECRET")
    @patch("requests.post")
    @patch("requests.get")
    def test_claim_already_connected(self, mock_get, mock_post):
        channel = Channel.objects.get(address="019283", channel_type="IG")
        self.assertEqual(channel.config[Channel.CONFIG_AUTH_TOKEN], "09876543")
        self.assertEqual(channel.config[Channel.CONFIG_PAGE_NAME], "FirstName")
        self.assertEqual(channel.config["page_id"], "123456")
        self.assertEqual(channel.name, "Instagram")

        name = "Temba"

        mock_get.side_effect = [
            MockResponse(200, json.dumps({"data": {"user_id": "098765", "expired_at": 100}})),
            MockResponse(200, json.dumps({"access_token": f"long-life-user-{self.token}"})),
            MockResponse(
                200,
                json.dumps(
                    {
                        "data": [
                            {
                                "name": name,
                                "id": "123456",
                                "access_token": self.long_life_page_token + "-updated",
                            }
                        ]
                    }
                ),
            ),
            MockResponse(
                200,
                json.dumps({"instagram_business_account": {"id": "019283"}, "id": "998776"}),
            ),
        ]

        mock_post.return_value = MockResponse(200, json.dumps({"success": True}))

        url = reverse("channels.types.instagram.claim")

        self.login(self.admin)

        # check that claim page URL appears on claim list page
        response = self.client.get(reverse("channels.channel_claim"))
        self.assertContains(response, url)

        # can fetch the claim page
        response = self.client.get(url)
        self.assertContains(response, "Connect Instagram")
        self.assertEqual(response.context["facebook_app_id"], "FB_APP_ID")
        self.assertEqual(response.context["claim_url"], url)

        post_data = response.context["form"].initial
        post_data["user_access_token"] = self.token
        post_data["page_id"] = "123456"
        post_data["page_name"] = name

        response = self.client.post(url, post_data, follow=True)
        channel = Channel.objects.get(address="019283", channel_type="IG")
        self.assertEqual(channel.config[Channel.CONFIG_AUTH_TOKEN], self.long_life_page_token + "-updated")
        self.assertEqual(channel.config[Channel.CONFIG_PAGE_NAME], "Temba")
        self.assertEqual(channel.config["page_id"], 123456)
        self.assertEqual(channel.name, "Instagram")

        mock_get.side_effect = [
            MockResponse(200, json.dumps({"data": {"user_id": "098765", "expired_at": 100}})),
            MockResponse(200, json.dumps({"access_token": f"long-life-user-{self.token}"})),
            MockResponse(
                200,
                json.dumps(
                    {
                        "data": [
                            {
                                "name": name,
                                "id": "123456",
                                "access_token": self.long_life_page_token,
                            }
                        ]
                    }
                ),
            ),
            MockResponse(
                200,
                json.dumps({"instagram_business_account": {"id": "019283"}, "id": "998776"}),
            ),
        ]

        self.login(self.admin2)

        # can fetch the claim page
        response = self.client.get(url)
        self.assertContains(response, "Connect Instagram")
        self.assertEqual(response.context["facebook_app_id"], "FB_APP_ID")
        self.assertEqual(response.context["claim_url"], url)

        post_data = response.context["form"].initial
        post_data["user_access_token"] = self.token
        post_data["page_id"] = "123456"
        post_data["page_name"] = name

        response = self.client.post(url, post_data, follow=True)
        self.assertContains(response, "This channel is already connected in another workspace.")

        mock_get.side_effect = [
            MockResponse(200, json.dumps({"data": {"user_id": "098765", "expired_at": 100}})),
            MockResponse(200, json.dumps({"access_token": f"long-life-user-{self.token}"})),
            MockResponse(
                200,
                json.dumps(
                    {
                        "data": [
                            {
                                "name": name,
                                "id": "123456",
                                "access_token": self.long_life_page_token,
                            }
                        ]
                    }
                ),
            ),
            MockResponse(
                200,
                json.dumps({"instagram_business_account": {"id": ""}, "id": "998776"}),
            ),
        ]

        # can fetch the claim page
        response = self.client.get(url)
        self.assertContains(response, "Connect Instagram")
        self.assertEqual(response.context["facebook_app_id"], "FB_APP_ID")
        self.assertEqual(response.context["claim_url"], url)

        post_data = response.context["form"].initial
        post_data["user_access_token"] = self.token
        post_data["page_id"] = "123456"
        post_data["page_name"] = name

        with self.assertRaises(AssertionError):
            response = self.client.post(url, post_data, follow=True)

    @patch("requests.delete")
    def test_release(self, mock_delete):
        mock_delete.return_value = MockResponse(200, json.dumps({"success": True}))
        self.channel.release(self.admin)

        mock_delete.assert_called_once_with(
            "https://graph.facebook.com/v18.0/019283/subscribed_apps",
            params={"access_token": "09876543"},
        )

    def test_get_error_ref_url(self):
        self.assertEqual(
            "https://developers.facebook.com/docs/instagram-api/reference/error-codes",
            InstagramType().get_error_ref_url(None, "36000"),
        )

    @override_settings(FACEBOOK_APPLICATION_ID="FB_APP_ID", FACEBOOK_APPLICATION_SECRET="FB_APP_SECRET")
    @patch("requests.get")
    def test_check_credentials(self, mock_get):
        check_credentials_url = reverse("channels.types.instagram.check_credentials", args=(self.channel.uuid,))

        self.login(self.admin)

        mock_get.return_value = MockResponse(200, json.dumps({"success": True, "data": {}}))
        response = self.client.get(check_credentials_url)
        self.assertContains(response, "Reconnect Instagram Business Account")
        self.assertContains(
            response,
            "Error with token, you need to reconnect the Instagram Business Account by clicking the button below",
        )
        self.assertEqual(response.context["update_token_url"], f"{reverse("channels.types.instagram.claim")}?update=1")
        self.assertFalse(response.context["valid_token"])

        mock_get.return_value = MockResponse(200, json.dumps({"success": True, "data": {"is_valid": True}}))

        response = self.client.get(check_credentials_url)
        self.assertContains(response, "Reconnect Instagram Business Account")
        self.assertContains(response, "Everything looks good. No need to reconnect")
        self.assertEqual(response.context["update_token_url"], f"{reverse("channels.types.instagram.claim")}?update=1")
        self.assertTrue(response.context["valid_token"])

    @override_settings(FACEBOOK_APPLICATION_ID="FB_APP_ID", FACEBOOK_APPLICATION_SECRET="FB_APP_SECRET")
    @patch("requests.get")
    def test_type_check_credentials(self, mock_get):
        self.assertFalse(InstagramType().check_credentials({}))

        mock_get.return_value = MockResponse(200, json.dumps({"success": True, "data": {}}))
        self.assertFalse(InstagramType().check_credentials({Channel.CONFIG_AUTH_TOKEN: "Token"}))

        mock_get.return_value = MockResponse(400, json.dumps({"error": True}))
        self.assertFalse(InstagramType().check_credentials({Channel.CONFIG_AUTH_TOKEN: "Token"}))

        mock_get.return_value = MockResponse(200, json.dumps({"success": True, "data": {"is_valid": True}}))
        self.assertTrue(InstagramType().check_credentials({Channel.CONFIG_AUTH_TOKEN: "Token"}))

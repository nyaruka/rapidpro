from unittest.mock import patch

from requests import RequestException

from django.forms import ValidationError
from django.urls import reverse

from temba.request_logs.models import HTTPLog
from temba.templates.models import TemplateTranslation
from temba.tests import MockResponse, TembaTest

from ...models import Channel
from .type import ZENVIA_MESSAGE_SUBSCRIPTION_ID, ZENVIA_STATUS_SUBSCRIPTION_ID, ZenviaWhatsAppType


class ZenviaWhatsAppTypeTest(TembaTest):
    def test_claim(self):
        Channel.objects.all().delete()

        self.login(self.admin)

        url = reverse("channels.types.zenvia_whatsapp.claim")

        # should see the general channel claim page
        response = self.client.get(reverse("channels.channel_claim"))
        self.assertContains(response, url)

        # try to claim a channel
        response = self.client.get(url)
        post_data = response.context["form"].initial

        post_data["token"] = "12345"
        post_data["country"] = "US"
        post_data["number"] = "(206) 555-1212"

        with patch("requests.get") as mock_get:
            mock_get.return_value = MockResponse(400, "Error")
            with patch("requests.post") as mock_post:
                mock_post.side_effect = [MockResponse(400, '{ "error": true }')]

                response = self.client.post(url, post_data)
                self.assertContains(response, "Please check your Zenvia account settings")

        with patch("requests.get") as mock_get:
            mock_get.return_value = MockResponse(200, "Success")
            with patch("requests.post") as mock_post:
                mock_post.side_effect = [MockResponse(400, '{ "error": true }')]

                with self.assertRaises(ValidationError):
                    self.client.post(url, post_data)

        with patch("requests.get") as mock_get:
            mock_get.return_value = MockResponse(200, "Success")
            with patch("requests.post") as mock_post:
                mock_post.side_effect = [
                    MockResponse(200, '{"id": "message_123"}'),
                    MockResponse(400, '{"error": "failed"}'),
                ]

                with self.assertRaises(ValidationError):
                    self.client.post(url, post_data)

                self.assertEqual("12345", mock_post.call_args_list[0][1]["headers"]["X-API-TOKEN"])

        with patch("requests.get") as mock_get:
            mock_get.return_value = MockResponse(200, "Success")
            with patch("requests.post") as mock_post:
                mock_post.side_effect = [
                    MockResponse(200, '{"id": "message_123"}'),
                    MockResponse(200, '{"id": "status_123"}'),
                ]

                self.client.post(url, post_data)

        channel = Channel.objects.get()

        self.assertEqual("US", channel.country)
        self.assertTrue(channel.uuid)
        self.assertEqual("+12065551212", channel.address)
        self.assertEqual("12345", channel.config["api_key"])
        self.assertEqual("ZVW", channel.channel_type)
        self.assertEqual("Zenvia WhatsApp: +12065551212", channel.name)

        with patch("requests.delete") as mock_delete:
            mock_delete.return_value = MockResponse(204, "")

            # deactivate our channel
            channel.release(self.admin)

            self.assertEqual(2, mock_delete.call_count)
            self.assertEqual(
                "https://api.zenvia.com/v2/subscriptions/message_123", mock_delete.call_args_list[0][0][0]
            )
            self.assertEqual("12345", mock_delete.call_args_list[0][1]["headers"]["X-API-TOKEN"])
            self.assertEqual("https://api.zenvia.com/v2/subscriptions/status_123", mock_delete.call_args_list[1][0][0])

        # try to claim a channel
        response = self.client.get(url)
        post_data = response.context["form"].initial

        post_data["token"] = "12345"
        post_data["country"] = "US"
        post_data["number"] = "(206) 555-1212"

        with patch("requests.get") as mock_get:
            mock_get.return_value = MockResponse(200, "Success")
            with patch("requests.post") as mock_post:
                mock_post.side_effect = [
                    MockResponse(200, '{"id": "message_123"}'),
                    MockResponse(200, '{"id": "status_123"}'),
                ]

                self.client.post(url, post_data)

        channel = Channel.objects.filter(is_active=True).first()

        self.assertEqual("12345", mock_post.call_args_list[0][1]["headers"]["X-API-TOKEN"])

        self.assertEqual("message_123", channel.config.get(ZENVIA_MESSAGE_SUBSCRIPTION_ID))
        self.assertEqual("status_123", channel.config.get(ZENVIA_STATUS_SUBSCRIPTION_ID))

        with patch("requests.delete") as mock_delete:
            mock_delete.return_value = MockResponse(400, "Error")

            # deactivate our channel
            channel.release(self.admin)

            self.assertEqual(2, mock_delete.call_count)
            self.assertEqual(
                "https://api.zenvia.com/v2/subscriptions/message_123", mock_delete.call_args_list[0][0][0]
            )
            self.assertEqual("12345", mock_delete.call_args_list[0][1]["headers"]["X-API-TOKEN"])
            self.assertEqual("https://api.zenvia.com/v2/subscriptions/status_123", mock_delete.call_args_list[1][0][0])
            self.assertEqual("12345", mock_delete.call_args_list[1][1]["headers"]["X-API-TOKEN"])

    @patch("requests.get")
    def test_get_api_templates(self, mock_get):
        TemplateTranslation.objects.all().delete()
        Channel.objects.all().delete()

        channel = self.create_channel(
            "ZVW",
            "Zenvia WhatsApp: +12065551212",
            "+12065551212",
            config={
                Channel.CONFIG_API_KEY: "authtoken123",
            },
        )

        mock_get.side_effect = [
            RequestException("Network is unreachable", response=MockResponse(100, "")),
            MockResponse(400, '{ "meta": { "success": false } }'),
            MockResponse(
                200,
                """[
                      {
                        "id": "string",
                        "name": "string",
                        "locale": "af",
                        "channel": "WHATSAPP",
                        "senderId": "string",
                        "category": "ACCOUNT_UPDATE",
                        "components": {
                          "header": {
                            "type": "MEDIA_DOCUMENT",
                            "text": "foo header"
                          },
                          "body": {
                            "type": "TEXT_FIXED",
                            "text": "foo body"
                          },
                          "footer": {
                            "type": "TEXT_FIXED",
                            "text": "foo footer"
                          },
                          "buttons": {
                            "type": "string",
                            "items": [
                              {
                                "type": "URL",
                                "text": "string",
                                "url": "string"
                              }
                            ]
                          }
                        },
                        "examples": {
                          "imageUrl": "https://example.com/image.jpeg",
                          "name": "John Smith"
                        },
                        "notificationEmail": "string",
                        "text": "string",
                        "fields": [
                          "string"
                        ],
                        "comments": [
                          {
                            "id": "string",
                            "author": "string",
                            "role": "REQUESTER",
                            "text": "string",
                            "createdAt": "string",
                            "updatedAt": "string"
                          }
                        ],
                        "status": "APPROVED",
                        "createdAt": "string",
                        "updatedAt": "string"
                      }
                    ]
                """,
            ),
        ]

        # RequestException check HTTPLog
        templates_data, no_error = ZenviaWhatsAppType().get_api_templates(channel)
        self.assertEqual(1, HTTPLog.objects.filter(log_type=HTTPLog.WHATSAPP_TEMPLATES_SYNCED).count())
        self.assertFalse(no_error)
        self.assertEqual([], templates_data)

        # should be empty list with an error flag if fail with API
        templates_data, no_error = ZenviaWhatsAppType().get_api_templates(channel)
        self.assertFalse(no_error)
        self.assertEqual([], templates_data)

        # success no error and list
        templates_data, no_error = ZenviaWhatsAppType().get_api_templates(channel)
        self.assertTrue(no_error)
        self.assertEqual(
            [
                {
                    "category": "ACCOUNT_UPDATE",
                    "components": [
                        {"text": "foo header", "type": "HEADER"},
                        {"text": "foo body", "type": "BODY"},
                        {"text": "foo footer", "type": "FOOTER"},
                    ],
                    "id": "string",
                    "language": "af",
                    "name": "string",
                    "status": "APPROVED",
                }
            ],
            templates_data,
        )

        mock_get.assert_called_with(
            "https://api.zenvia.com/v2/templates",
            headers={"X-API-TOKEN": "authtoken123", "Content-Type": "application/json"},
        )

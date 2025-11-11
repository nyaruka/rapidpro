import json
from unittest.mock import call, patch

from requests import RequestException

from temba.request_logs.models import HTTPLog
from temba.templates.models import TemplateTranslation
from temba.tests import CRUDLTestMixin, MockResponse, TembaTest

from ...models import Channel
from .tasks import refresh_whatsapp_tokens
from .type import CONFIG_FB_ACCESS_TOKEN, CONFIG_FB_BUSINESS_ID, CONFIG_FB_NAMESPACE, CONFIG_FB_TEMPLATE_LIST_DOMAIN


class WhatsAppLegacyTypeTest(CRUDLTestMixin, TembaTest):
    def test_refresh_tokens(self):
        TemplateTranslation.objects.all().delete()
        Channel.objects.all().delete()

        channel = self.create_channel(
            "WA",
            "WhatsApp: 1234",
            "1234",
            config={
                Channel.CONFIG_BASE_URL: "https://textit.com/whatsapp",
                Channel.CONFIG_USERNAME: "temba",
                Channel.CONFIG_PASSWORD: "tembapasswd",
                Channel.CONFIG_AUTH_TOKEN: "authtoken123",
                CONFIG_FB_BUSINESS_ID: "1234",
                CONFIG_FB_ACCESS_TOKEN: "token123",
                CONFIG_FB_NAMESPACE: "my-custom-app",
                CONFIG_FB_TEMPLATE_LIST_DOMAIN: "graph.facebook.com",
            },
        )

        channel2 = self.create_channel(
            "WA",
            "WhatsApp: 1235",
            "1235",
            config={
                Channel.CONFIG_BASE_URL: "https://textit.com/whatsapp",
                Channel.CONFIG_USERNAME: "temba",
                Channel.CONFIG_PASSWORD: "tembapasswd",
                Channel.CONFIG_AUTH_TOKEN: "authtoken123",
                CONFIG_FB_BUSINESS_ID: "1234",
                CONFIG_FB_ACCESS_TOKEN: "token123",
                CONFIG_FB_NAMESPACE: "my-custom-app",
                CONFIG_FB_TEMPLATE_LIST_DOMAIN: "graph.facebook.com",
            },
        )

        # and fetching new tokens
        with patch("requests.post") as mock_post:
            mock_post.return_value = MockResponse(
                200,
                '{"users": [{"token": "abc345"}]}',
                headers={
                    "Authorization": "Basic dGVtYmE6dGVtYmFwYXNzd2Q=",
                    "WA-user": "temba",
                    "WA-pass": "tembapasswd",
                },
            )
            self.assertFalse(channel.http_logs.filter(log_type=HTTPLog.WHATSAPP_TOKENS_SYNCED, is_error=False))
            refresh_whatsapp_tokens()
            self.assertTrue(channel.http_logs.filter(log_type=HTTPLog.WHATSAPP_TOKENS_SYNCED, is_error=False))
            channel.refresh_from_db()
            self.assertEqual("abc345", channel.config[Channel.CONFIG_AUTH_TOKEN])
            # check channel username, password, basic auth are redacted in HTTP logs
            for log in channel.http_logs.all():
                self.assertIn("temba", json.dumps(log.get_display()))
                self.assertNotIn("tembapasswd", json.dumps(log.get_display()))
                self.assertNotIn("dGVtYmE6dGVtYmFwYXNzd2Q=", json.dumps(log.get_display()))

        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                MockResponse(
                    400,
                    '{ "error": true }',
                    headers={
                        "Authorization": "Basic dGVtYmE6dGVtYmFwYXNzd2Q=",
                        "WA-user": "temba",
                        "WA-pass": "tembapasswd",
                    },
                )
            ]
            self.assertFalse(channel.http_logs.filter(log_type=HTTPLog.WHATSAPP_TOKENS_SYNCED, is_error=True))
            refresh_whatsapp_tokens()
            self.assertTrue(channel.http_logs.filter(log_type=HTTPLog.WHATSAPP_TOKENS_SYNCED, is_error=True))
            channel.refresh_from_db()
            self.assertEqual("abc345", channel.config[Channel.CONFIG_AUTH_TOKEN])
            # check channel username, password, basic auth are redacted in HTTP logs
            for log in channel.http_logs.all():
                self.assertIn("temba", json.dumps(log.get_display()))
                self.assertNotIn("tembapasswd", json.dumps(log.get_display()))
                self.assertNotIn("dGVtYmE6dGVtYmFwYXNzd2Q=", json.dumps(log.get_display()))

        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                MockResponse(
                    200,
                    "",
                    headers={
                        "Authorization": "Basic dGVtYmE6dGVtYmFwYXNzd2Q=",
                        "WA-user": "temba",
                        "WA-pass": "tembapasswd",
                    },
                ),
                MockResponse(
                    200,
                    '{"users": [{"token": "abc098"}]}',
                    headers={
                        "Authorization": "Basic dGVtYmE6dGVtYmFwYXNzd2Q=",
                        "WA-user": "temba",
                        "WA-pass": "tembapasswd",
                    },
                ),
            ]
            refresh_whatsapp_tokens()

            channel.refresh_from_db()
            channel2.refresh_from_db()
            self.assertEqual("abc345", channel.config[Channel.CONFIG_AUTH_TOKEN])
            self.assertEqual("abc098", channel2.config[Channel.CONFIG_AUTH_TOKEN])
            # check channel username, password, basic auth are redacted in HTTP logs
            for log in channel.http_logs.all():
                self.assertIn("temba", json.dumps(log.get_display()))
                self.assertNotIn("tembapasswd", json.dumps(log.get_display()))
                self.assertNotIn("dGVtYmE6dGVtYmFwYXNzd2Q=", json.dumps(log.get_display()))
            for log in channel2.http_logs.all():
                self.assertIn("temba", json.dumps(log.get_display()))
                self.assertNotIn("tembapasswd", json.dumps(log.get_display()))
                self.assertNotIn("dGVtYmE6dGVtYmFwYXNzd2Q=", json.dumps(log.get_display()))

    @patch("requests.get")
    def test_fetch_templates(self, mock_get):
        channel = self.create_channel(
            "WA",
            "WhatsApp: 1234",
            "1234",
            config={
                Channel.CONFIG_BASE_URL: "https://textit.com/whatsapp",
                Channel.CONFIG_USERNAME: "temba",
                Channel.CONFIG_PASSWORD: "tembapasswd",
                Channel.CONFIG_AUTH_TOKEN: "authtoken123",
                CONFIG_FB_BUSINESS_ID: "1234",
                CONFIG_FB_ACCESS_TOKEN: "token123",
                CONFIG_FB_NAMESPACE: "my-custom-app",
                CONFIG_FB_TEMPLATE_LIST_DOMAIN: "graph.facebook.com",
            },
        )

        mock_get.side_effect = [
            RequestException("Network is unreachable", response=MockResponse(100, "")),
            MockResponse(400, '{ "meta": { "success": false } }'),
            MockResponse(200, '{"data": ["foo", "bar"]}'),
            MockResponse(
                200,
                '{"data": ["foo"], "paging": {"next": "https://graph.facebook.com/v14.0/1234/message_templates?cursor=MjQZD"} }',
            ),
            MockResponse(200, '{"data": ["bar"], "paging": {"next": null} }'),
        ]

        with self.assertRaises(RequestException):
            channel.type.fetch_templates(channel)

        self.assertEqual(1, HTTPLog.objects.filter(log_type=HTTPLog.WHATSAPP_TEMPLATES_SYNCED, is_error=True).count())

        with self.assertRaises(RequestException):
            channel.type.fetch_templates(channel)

        self.assertEqual(2, HTTPLog.objects.filter(log_type=HTTPLog.WHATSAPP_TEMPLATES_SYNCED, is_error=True).count())

        # check when no next page
        templates = channel.type.fetch_templates(channel)
        self.assertEqual(["foo", "bar"], templates)

        self.assertEqual(2, HTTPLog.objects.filter(log_type=HTTPLog.WHATSAPP_TEMPLATES_SYNCED, is_error=True).count())
        self.assertEqual(1, HTTPLog.objects.filter(log_type=HTTPLog.WHATSAPP_TEMPLATES_SYNCED, is_error=False).count())

        # check admin token is redacted in HTTP logs
        for log in HTTPLog.objects.all():
            self.assertNotIn("token123", json.dumps(log.get_display()))

        mock_get.assert_called_with(
            "https://graph.facebook.com/v14.0/1234/message_templates",
            params={"access_token": "token123", "limit": 255},
        )

        # check when templates across two pages
        templates = channel.type.fetch_templates(channel)
        self.assertEqual(["foo", "bar"], templates)

        mock_get.assert_has_calls(
            [
                call(
                    "https://graph.facebook.com/v14.0/1234/message_templates",
                    params={"access_token": "token123", "limit": 255},
                ),
                call(
                    "https://graph.facebook.com/v14.0/1234/message_templates?cursor=MjQZD",
                    params={"access_token": "token123", "limit": 255},
                ),
            ]
        )

    def test_check_health(self):
        channel = self.create_channel(
            "WA",
            "WhatsApp: 1234",
            "1234",
            config={
                Channel.CONFIG_BASE_URL: "https://textit.com/whatsapp",
                Channel.CONFIG_USERNAME: "temba",
                Channel.CONFIG_PASSWORD: "tembapasswd",
                Channel.CONFIG_AUTH_TOKEN: "authtoken123",
                CONFIG_FB_BUSINESS_ID: "1234",
                CONFIG_FB_ACCESS_TOKEN: "token123",
                CONFIG_FB_NAMESPACE: "my-custom-app",
                CONFIG_FB_TEMPLATE_LIST_DOMAIN: "graph.facebook.com",
            },
        )

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                RequestException("Network is unreachable", response=MockResponse(100, "")),
                MockResponse(200, '{"meta": {"api_status": "stable", "version": "v2.35.2"}}'),
                MockResponse(401, ""),
            ]

            with patch("logging.Logger.debug") as mock_log_debug:
                channel.type.check_health(channel)
                self.assertEqual(1, mock_log_debug.call_count)
                self.assertEqual(
                    "Could not establish a connection with the WhatsApp server: Network is unreachable",
                    mock_log_debug.call_args[0][0],
                )

            channel.type.check_health(channel)
            mock_get.assert_called_with(
                "https://textit.com/whatsapp/v1/health", headers={"Authorization": "Bearer authtoken123"}
            )

            with patch("logging.Logger.debug") as mock_log_debug:
                channel.type.check_health(channel)
                self.assertEqual(1, mock_log_debug.call_count)
                self.assertEqual(
                    "Error checking API health: b''",
                    mock_log_debug.call_args[0][0],
                )

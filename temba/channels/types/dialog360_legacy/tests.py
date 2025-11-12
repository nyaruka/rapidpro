import json
from unittest.mock import patch

from requests import RequestException

from temba.request_logs.models import HTTPLog
from temba.tests import CRUDLTestMixin, MockResponse, TembaTest

from ...models import Channel


class Dialog360LegacyTypeTest(CRUDLTestMixin, TembaTest):
    @patch("requests.get")
    def test_fetch_templates(self, mock_get):
        channel = self.create_channel(
            "D3",
            "360Dialog channel",
            address="1234",
            country="BR",
            config={
                Channel.CONFIG_BASE_URL: "https://example.com/whatsapp",
                Channel.CONFIG_AUTH_TOKEN: "123456789",
            },
        )

        mock_get.side_effect = [
            RequestException("Network is unreachable", response=MockResponse(100, "")),
            MockResponse(400, '{ "meta": { "success": false } }', headers={"D360-API-KEY": "123456789"}),
            MockResponse(200, '{"waba_templates": ["foo", "bar"]}', headers={"D360-API-KEY": "123456789"}),
        ]

        with self.assertRaises(RequestException):
            channel.type.fetch_templates(channel)

        self.assertEqual(1, HTTPLog.objects.filter(log_type=HTTPLog.WHATSAPP_TEMPLATES_SYNCED, is_error=True).count())

        with self.assertRaises(RequestException):
            channel.type.fetch_templates(channel)

        self.assertEqual(2, HTTPLog.objects.filter(log_type=HTTPLog.WHATSAPP_TEMPLATES_SYNCED, is_error=True).count())

        templates = channel.type.fetch_templates(channel)
        self.assertEqual(["foo", "bar"], templates)

        self.assertEqual(2, HTTPLog.objects.filter(log_type=HTTPLog.WHATSAPP_TEMPLATES_SYNCED, is_error=True).count())
        self.assertEqual(1, HTTPLog.objects.filter(log_type=HTTPLog.WHATSAPP_TEMPLATES_SYNCED, is_error=False).count())

        # check auth token is redacted in HTTP logs
        for log in HTTPLog.objects.all():
            self.assertNotIn("123456789", json.dumps(log.get_display()))

        mock_get.assert_called_with(
            "https://example.com/whatsapp/v1/configs/templates",
            headers={
                "D360-API-KEY": channel.config[Channel.CONFIG_AUTH_TOKEN],
                "Content-Type": "application/json",
            },
        )

    def test_check_health(self):
        channel = self.create_channel(
            "D3",
            "360Dialog channel",
            address="1234",
            country="BR",
            config={
                Channel.CONFIG_BASE_URL: "https://example.com/whatsapp",
                Channel.CONFIG_AUTH_TOKEN: "123456789",
            },
        )
        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                MockResponse(200, '{"meta": {"api_status": "stable", "version": "2.35.4"}}'),
                MockResponse(401, ""),
            ]
            channel.type.check_health(channel)
            mock_get.assert_called_with(
                "https://example.com/whatsapp/v1/health",
                headers={"D360-API-KEY": "123456789", "Content-Type": "application/json"},
            )

            with patch("logging.Logger.debug") as mock_log_debug:
                channel.type.check_health(channel)
                self.assertEqual(1, mock_log_debug.call_count)
                self.assertEqual(
                    "Error checking API health: b''",
                    mock_log_debug.call_args[0][0],
                )

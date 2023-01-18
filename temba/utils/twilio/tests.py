from unittest.mock import patch

from django.urls import reverse

from temba.channels.models import Channel
from temba.tests import CRUDLTestMixin, TembaTest
from temba.tests.twilio import MockRequestValidator, MockTwilioClient


class TwilioUtilsTest(TembaTest, CRUDLTestMixin):
    @patch("temba.utils.twilio.views.TwilioClient", MockTwilioClient)
    @patch("twilio.request_validator.RequestValidator", MockRequestValidator)
    def test_twilio_update_credentials(self):
        self.login(self.admin)

        config = {
            Channel.CONFIG_APPLICATION_SID: "app-sid",
            Channel.CONFIG_NUMBER_SID: "number-sid",
            Channel.CONFIG_ACCOUNT_SID: "account-sid",
            Channel.CONFIG_AUTH_TOKEN: "account-token",
            Channel.CONFIG_CALLBACK_DOMAIN: "rapidpro.io",
        }

        channel = self.create_channel("T", "channel", "1234", config=config)

        update_credentials_url = reverse("channels.types.twilio.update_credentials", args=[channel.uuid])

        self.assertUpdateFetch(
            update_credentials_url,
            allow_viewers=False,
            allow_editors=True,
            form_fields={"account_sid": "account-sid", "account_token": "account-token"},
        )

        with patch("temba.tests.twilio.MockTwilioClient.MockPhoneNumbers.stream") as mock_numbers:
            mock_numbers.return_value = iter([])

            with patch("temba.tests.twilio.MockTwilioClient.MockShortCodes.stream") as mock_short_codes:
                mock_short_codes.return_value = iter([MockTwilioClient.MockShortCode("8080")])

                self.assertUpdateSubmit(
                    update_credentials_url,
                    {"account_sid": "AccountSid", "account_token": "AccountToken"},
                )
                channel.refresh_from_db()
                channel_config = channel.config
                self.assertEqual(channel_config[Channel.CONFIG_ACCOUNT_SID], "AccountSid")
                self.assertEqual(channel_config[Channel.CONFIG_AUTH_TOKEN], "AccountToken")
                self.assertEqual(channel_config[Channel.CONFIG_APPLICATION_SID], "TwilioTestSid")
                self.assertEqual(channel_config[Channel.CONFIG_NUMBER_SID], "ShortSid")

        channel = self.create_channel("T", "channel", "12062345678", config=config)

        update_credentials_url = reverse("channels.types.twilio.update_credentials", args=[channel.uuid])

        self.assertUpdateFetch(
            update_credentials_url,
            allow_viewers=False,
            allow_editors=True,
            form_fields={"account_sid": "account-sid", "account_token": "account-token"},
        )

        channel.refresh_from_db()
        channel_config = channel.config
        self.assertEqual(channel_config[Channel.CONFIG_ACCOUNT_SID], "account-sid")
        self.assertEqual(channel_config[Channel.CONFIG_AUTH_TOKEN], "account-token")
        self.assertEqual(channel_config[Channel.CONFIG_APPLICATION_SID], "app-sid")
        self.assertEqual(channel_config[Channel.CONFIG_NUMBER_SID], "number-sid")

        with patch("temba.tests.twilio.MockTwilioClient.MockPhoneNumbers.stream") as mock_numbers:
            mock_numbers.return_value = iter([MockTwilioClient.MockPhoneNumber("+12062345678")])

            with patch("temba.tests.twilio.MockTwilioClient.MockShortCodes.stream") as mock_short_codes:
                mock_short_codes.return_value = iter([])

                self.assertUpdateSubmit(
                    update_credentials_url,
                    {"account_sid": "AccountSid", "account_token": "AccountToken"},
                )
                channel.refresh_from_db()
                channel_config = channel.config
                self.assertEqual(channel_config[Channel.CONFIG_ACCOUNT_SID], "AccountSid")
                self.assertEqual(channel_config[Channel.CONFIG_AUTH_TOKEN], "AccountToken")
                self.assertEqual(channel_config[Channel.CONFIG_APPLICATION_SID], "TwilioTestSid")
                self.assertEqual(channel_config[Channel.CONFIG_NUMBER_SID], "PhoneNumberSid")

    @patch("temba.utils.twilio.views.TwilioClient", MockTwilioClient)
    @patch("twilio.request_validator.RequestValidator", MockRequestValidator)
    def test_twilio_whatsapp_update_credentials(self):
        self.login(self.admin)

        config = {
            Channel.CONFIG_NUMBER_SID: "number-sid",
            Channel.CONFIG_ACCOUNT_SID: "account-sid",
            Channel.CONFIG_AUTH_TOKEN: "account-token",
            Channel.CONFIG_CALLBACK_DOMAIN: "rapidpro.io",
        }

        channel = self.create_channel("TWA", "channel", "1234", config=config)

        update_credentials_url = reverse("channels.types.twilio_whatsapp.update_credentials", args=[channel.uuid])

        self.assertUpdateFetch(
            update_credentials_url,
            allow_viewers=False,
            allow_editors=True,
            form_fields={"account_sid": "account-sid", "account_token": "account-token"},
        )

        with patch("temba.tests.twilio.MockTwilioClient.MockPhoneNumbers.stream") as mock_numbers:
            mock_numbers.return_value = iter([MockTwilioClient.MockPhoneNumber("+12062345678")])

            self.assertUpdateSubmit(
                update_credentials_url,
                {"account_sid": "AccountSid", "account_token": "AccountToken"},
            )
            channel.refresh_from_db()
            channel_config = channel.config
            self.assertEqual(channel_config[Channel.CONFIG_ACCOUNT_SID], "AccountSid")
            self.assertEqual(channel_config[Channel.CONFIG_AUTH_TOKEN], "AccountToken")
            # TWA number SID should have not changedon the same Twilio account, no support for number moved on Twilio
            self.assertEqual(channel_config[Channel.CONFIG_NUMBER_SID], "number-sid")
            self.assertFalse(Channel.CONFIG_APPLICATION_SID in channel_config)

    @patch("temba.utils.twilio.views.TwilioClient", MockTwilioClient)
    @patch("twilio.request_validator.RequestValidator", MockRequestValidator)
    def test_twilio_messaging_service_update_credentials(self):
        self.login(self.admin)

        config = {
            Channel.CONFIG_MESSAGING_SERVICE_SID: "messaging-sid",
            Channel.CONFIG_ACCOUNT_SID: "account-sid",
            Channel.CONFIG_AUTH_TOKEN: "account-token",
            Channel.CONFIG_CALLBACK_DOMAIN: "rapidpro.io",
        }

        channel = self.create_channel("TMS", "channel", "1234", config=config)

        update_credentials_url = reverse(
            "channels.types.twilio_messaging_service.update_credentials", args=[channel.uuid]
        )

        self.assertUpdateFetch(
            update_credentials_url,
            allow_viewers=False,
            allow_editors=True,
            form_fields={"account_sid": "account-sid", "account_token": "account-token"},
        )

        self.assertUpdateSubmit(
            update_credentials_url,
            {"account_sid": "AccountSid", "account_token": "AccountToken"},
        )
        channel.refresh_from_db()
        channel_config = channel.config
        self.assertEqual(channel_config[Channel.CONFIG_ACCOUNT_SID], "AccountSid")
        self.assertEqual(channel_config[Channel.CONFIG_AUTH_TOKEN], "AccountToken")
        self.assertEqual(
            channel_config[Channel.CONFIG_MESSAGING_SERVICE_SID], "messaging-sid"
        )  # we do not change that
        self.assertFalse(Channel.CONFIG_APPLICATION_SID in channel_config)
        self.assertFalse(Channel.CONFIG_NUMBER_SID in channel_config)

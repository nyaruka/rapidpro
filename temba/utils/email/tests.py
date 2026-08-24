import smtplib
from unittest.mock import patch

from django.core import mail
from django.test.utils import override_settings

from temba.tests import TembaTest

from .conf import make_smtp_url, parse_smtp_url
from .send import EmailSender, send_via_smtp

LOCMEM = {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}
DUMMY = {"BACKEND": "django.core.mail.backends.dummy.EmailBackend"}


class EmailTest(TembaTest):
    def test_sender(self):
        branding = {"name": "Test", "emails": {"spam": "no-reply@acme.com"}}
        sender = EmailSender.from_email_type(branding, "spam")
        self.assertEqual(branding, sender.branding)
        self.assertEqual("no-reply@acme.com", sender.from_email)
        self.assertEqual("default", sender.mailer)  # no mailer of that name so use default

        # test email type not defined in branding
        sender = EmailSender.from_email_type(branding, "marketing")
        self.assertEqual(branding, sender.branding)
        self.assertEqual("Temba <server@temba.io>", sender.from_email)  # from settings
        self.assertEqual("default", sender.mailer)

        # test email type which has its own mailer
        with override_settings(MAILERS={"default": LOCMEM, "spam": LOCMEM}):
            sender = EmailSender.from_email_type(branding, "spam")
            self.assertEqual("no-reply@acme.com", sender.from_email)
            self.assertEqual("spam", sender.mailer)

    def test_send(self):
        branding = {"name": "Test", "emails": {"notifications": "no-reply@acme.com"}}
        sender = EmailSender.from_email_type(branding, "notifications")
        sender.send(["bob@acme.com"], "orgs/email/smtp_test", {}, "Hello")

        self.assertEqual(1, len(mail.outbox))
        self.assertEqual("Hello", mail.outbox[0].subject)
        self.assertEqual("no-reply@acme.com", mail.outbox[0].from_email)
        self.assertEqual(["bob@acme.com"], mail.outbox[0].to)
        self.assertEqual("text/html", mail.outbox[0].alternatives[0].mimetype)

        # if there's a mailer named after the email type, it's used instead of the default
        with override_settings(MAILERS={"default": DUMMY, "notifications": LOCMEM}):
            EmailSender.from_email_type(branding, "notifications").send(
                ["bob@acme.com"], "orgs/email/smtp_test", {}, "Via notifications"
            )

            self.assertEqual(2, len(mail.outbox))
            self.assertEqual("Via notifications", mail.outbox[1].subject)

        # and the default mailer isn't used for that email type even if it could deliver
        with override_settings(MAILERS={"default": LOCMEM, "notifications": DUMMY}):
            EmailSender.from_email_type(branding, "notifications").send(
                ["bob@acme.com"], "orgs/email/smtp_test", {}, "Not delivered here"
            )

            self.assertEqual(2, len(mail.outbox))  # went to the notifications mailer which discards

    def test_send_via_smtp(self):
        branding = {"name": "Test", "emails": {}}
        message = EmailSender(branding, from_email="no-reply@acme.com").compose(
            ["bob@acme.com"], "orgs/email/smtp_test", {}, "Hello"
        )

        with patch("smtplib.SMTP") as mock_smtp:
            send_via_smtp("smtp://jim%40acme.com:sesame@mail.acme.com:587/?tls=true", message)

            self.assertEqual(("mail.acme.com", 587), mock_smtp.call_args.args)

            conn = mock_smtp.return_value.__enter__.return_value
            conn.starttls.assert_called_once()
            conn.login.assert_called_once_with("jim@acme.com", "sesame")

            sent = conn.send_message.call_args.args[0]
            self.assertEqual("Hello", sent["Subject"])
            self.assertEqual("no-reply@acme.com", sent["From"])
            self.assertEqual("bob@acme.com", sent["To"])

        # SMTP config without TLS or credentials
        with patch("smtplib.SMTP") as mock_smtp:
            send_via_smtp("smtp://mail.acme.com:25/", message)

            conn = mock_smtp.return_value.__enter__.return_value
            conn.starttls.assert_not_called()
            conn.login.assert_not_called()
            conn.send_message.assert_called_once()

        # errors from the server are not swallowed
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__.return_value.login.side_effect = smtplib.SMTPAuthenticationError(
                535, "nope"
            )

            with self.assertRaises(smtplib.SMTPAuthenticationError):
                send_via_smtp("smtp://jim:sesame@mail.acme.com:587/?tls=true", message)

        self.assertEqual(0, len(mail.outbox))  # nothing sent via a configured mailer

    def test_make_smtp_url(self):
        self.assertEqual(
            "smtp://foo:sesame@gmail.com:25/",
            make_smtp_url("gmail.com", 25, "foo", "sesame", from_email=None, tls=False),
        )
        self.assertEqual(
            "smtp://foo%25:ses%2Fame@gmail.com:457/?from=foo%40gmail.com&tls=true",
            make_smtp_url("gmail.com", 457, "foo%", "ses/ame", "foo@gmail.com", tls=True),
        )

    def test_parse_smtp_url(self):
        self.assertEqual((None, 25, None, None, None, False), parse_smtp_url(None))
        self.assertEqual((None, 25, None, None, None, False), parse_smtp_url(""))
        self.assertEqual(
            ("gmail.com", 25, "foo", "sesame", None, False),
            parse_smtp_url("smtp://foo:sesame@gmail.com/?tls=false"),
        )
        self.assertEqual(
            ("gmail.com", 25, "foo", "sesame", None, True),
            parse_smtp_url("smtp://foo:sesame@gmail.com:25/?tls=true"),
        )
        self.assertEqual(
            ("gmail.com", 457, "foo%", "ses/ame", "foo@gmail.com", True),
            parse_smtp_url("smtp://foo%25:ses%2Fame@gmail.com:457/?tls=true&from=foo%40gmail.com"),
        )
        self.assertEqual((None, 25, None, None, "foo@gmail.com", False), parse_smtp_url("smtp://?from=foo%40gmail.com"))

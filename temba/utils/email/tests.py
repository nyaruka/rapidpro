import smtplib
from unittest.mock import patch

from django.core import mail
from django.core.mail import EmailMultiAlternatives, mailers
from django.test.utils import override_settings

from temba.tests import TembaTest

from .conf import make_smtp_url, parse_smtp_url
from .send import EmailSender

LOCMEM = {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}
DUMMY = {"BACKEND": "django.core.mail.backends.dummy.EmailBackend"}
DYNAMIC = {"BACKEND": "temba.utils.email.backend.DynamicEmailBackend"}


class EmailTest(TembaTest):
    def test_sender(self):
        branding = {"name": "Test", "emails": {"spam": "no-reply@acme.com"}}
        sender = EmailSender.from_email_type(branding, "spam")
        self.assertEqual(branding, sender.branding)
        self.assertEqual("no-reply@acme.com", sender.from_email)
        self.assertIsNone(sender.smtp_url)  # will use default mailer

        # test email type not defined in branding
        sender = EmailSender.from_email_type(branding, "marketing")
        self.assertEqual(branding, sender.branding)
        self.assertEqual("Temba <server@temba.io>", sender.from_email)  # from settings
        self.assertIsNone(sender.smtp_url)

        # test full SMTP url in branding
        branding = {"name": "Test", "emails": {"spam": "smtp://foo:sesame@acme.com/?tls=true&from=no-reply%40acme.com"}}
        sender = EmailSender.from_email_type(branding, "spam")
        self.assertEqual(branding, sender.branding)
        self.assertEqual("no-reply@acme.com", sender.from_email)
        self.assertEqual("smtp://foo:sesame@acme.com/?tls=true&from=no-reply%40acme.com", sender.smtp_url)

    def test_send(self):
        # a sender without SMTP config sends via the default mailer
        branding = {"name": "Test", "emails": {"notifications": "no-reply@acme.com"}}
        with override_settings(MAILERS={"default": LOCMEM, "dynamic": DUMMY}):
            EmailSender.from_email_type(branding, "notifications").send(
                ["bob@acme.com"], "orgs/email/smtp_test", {}, "Hello"
            )

        self.assertEqual(1, len(mail.outbox))
        self.assertEqual("Hello", mail.outbox[0].subject)
        self.assertEqual("no-reply@acme.com", mail.outbox[0].from_email)
        self.assertEqual(["bob@acme.com"], mail.outbox[0].to)
        self.assertEqual("text/html", mail.outbox[0].alternatives[0].mimetype)

        # a sender with SMTP config attaches it to the message and sends via the dynamic mailer
        smtp_url = "smtp://foo:sesame@acme.com/?tls=true&from=no-reply%40acme.com"
        branding = {"name": "Test", "emails": {"notifications": smtp_url}}
        with override_settings(MAILERS={"default": DUMMY, "dynamic": LOCMEM}):
            EmailSender.from_email_type(branding, "notifications").send(
                ["bob@acme.com"], "orgs/email/smtp_test", {}, "Via dynamic"
            )

        self.assertEqual(2, len(mail.outbox))
        self.assertEqual("Via dynamic", mail.outbox[1].subject)
        self.assertEqual(smtp_url, mail.outbox[1].smtp_url)

    def test_dynamic_backend(self):
        def compose(subject: str) -> EmailMultiAlternatives:
            message = EmailMultiAlternatives(subject, "hi", "no-reply@acme.com", ["bob@acme.com"])
            message.attach_alternative("<p>hi</p>", "text/html")
            return message

        with override_settings(MAILERS={"default": LOCMEM, "dynamic": DYNAMIC}):
            backend = mailers["dynamic"]

            # messages are sent using the SMTP configuration attached to them
            message = compose("Hello")
            message.smtp_url = "smtp://jim%40acme.com:sesame@mail.acme.com:587/?tls=true"

            with patch("smtplib.SMTP") as mock_smtp:
                self.assertEqual(1, backend.send_messages([message]))

                self.assertEqual(("mail.acme.com", 587), mock_smtp.call_args.args)

                conn = mock_smtp.return_value.__enter__.return_value
                conn.starttls.assert_called_once()
                conn.login.assert_called_once_with("jim@acme.com", "sesame")

                sent = conn.send_message.call_args.args[0]
                self.assertEqual("Hello", sent["Subject"])
                self.assertEqual("no-reply@acme.com", sent["From"])
                self.assertEqual("bob@acme.com", sent["To"])

            # SMTP configuration without TLS or credentials
            message = compose("Hello")
            message.smtp_url = "smtp://mail.acme.com:25/"

            with patch("smtplib.SMTP") as mock_smtp:
                self.assertEqual(1, backend.send_messages([message]))

                conn = mock_smtp.return_value.__enter__.return_value
                conn.starttls.assert_not_called()
                conn.login.assert_not_called()
                conn.send_message.assert_called_once()

            # errors from the server are not swallowed
            message = compose("Hello")
            message.smtp_url = "smtp://jim:sesame@mail.acme.com:587/?tls=true"

            with patch("smtplib.SMTP") as mock_smtp:
                mock_smtp.return_value.__enter__.return_value.login.side_effect = smtplib.SMTPAuthenticationError(
                    535, "nope"
                )

                with self.assertRaises(smtplib.SMTPAuthenticationError):
                    backend.send_messages([message])

            # messages without attached SMTP configuration can't be sent
            with self.assertRaises(ValueError):
                backend.send_messages([compose("Hello")])

        self.assertEqual(0, len(mail.outbox))  # nothing sent via the default mailer

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

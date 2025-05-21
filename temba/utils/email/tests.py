from temba.tests import TembaTest

from .conf import make_smtp_url, parse_smtp_url
from .send import EmailSender


class EmailTest(TembaTest):
    def test_sender(self):
        branding = {"name": "Test", "emails": {"spam": "no-reply@acme.com"}}
        sender = EmailSender.from_email_type(branding, "spam")
        self.assertEqual(branding, sender.branding)
        self.assertIsNone(sender.connection)  # use default
        self.assertEqual("no-reply@acme.com", sender.from_email)

        # test email type not defined in branding
        sender = EmailSender.from_email_type(branding, "marketing")
        self.assertEqual(branding, sender.branding)
        self.assertIsNone(sender.connection)
        self.assertEqual("Temba <server@temba.io>", sender.from_email)  # from settings

        # test full SMTP url in branding
        branding = {"name": "Test", "emails": {"spam": "smtp://foo:sesame@acme.com/?tls=true&from=no-reply%40acme.com"}}
        sender = EmailSender.from_email_type(branding, "spam")
        self.assertEqual(branding, sender.branding)
        self.assertIsNotNone(sender.connection)
        self.assertEqual("no-reply@acme.com", sender.from_email)

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

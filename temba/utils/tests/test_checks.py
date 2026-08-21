from django.test import override_settings

from temba.tests import TembaTest
from temba.utils.checks import branding_emails, storage


class SystemChecksTest(TembaTest):
    def test_storage(self):
        self.assertEqual(len(storage(None)), 0)

        with override_settings(STORAGES={"default": {"BACKEND": "x"}, "staticfiles": {"BACKEND": "x"}}):
            self.assertEqual(storage(None)[0].msg, "Missing 'archives' storage config.")
            self.assertEqual(storage(None)[1].msg, "Missing 'public' storage config.")

        with override_settings(STORAGE_URL=None):
            self.assertEqual(storage(None)[0].msg, "No storage URL set.")

        with override_settings(STORAGE_URL="http://example.com/uploads/"):
            self.assertEqual(storage(None)[0].msg, "Storage URL shouldn't end with trailing slash.")

    def test_branding_emails(self):
        self.assertEqual(len(branding_emails(None)), 0)

        with override_settings(BRAND={"emails": {"notifications": "smtp://bob:sesame@example.com/"}}):
            self.assertEqual(branding_emails(None)[0].msg, "Branding email address for 'notifications' is an SMTP URL.")

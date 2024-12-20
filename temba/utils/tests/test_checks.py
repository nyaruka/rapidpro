from django.test import override_settings

from temba.tests import TembaTest
from temba.utils.checks import storage


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

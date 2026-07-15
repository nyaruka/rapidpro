from django.urls import reverse

from temba.tests.base import TembaTest


class UserSettingsTest(TembaTest):
    def test_settings(self):
        settings_url = reverse("users.user_settings")

        # must be logged in
        response = self.client.post(settings_url, {}, content_type="application/json")
        self.assertEqual(302, response.status_code)

        self.login(self.admin)

        # body must be a JSON object
        response = self.client.post(settings_url, "notjson", content_type="application/json")
        self.assertEqual(400, response.status_code)

        response = self.client.post(settings_url, [1, 2], content_type="application/json")
        self.assertEqual(400, response.status_code)

        # and not absurdly large
        response = self.client.post(settings_url, {"blob": "x" * 200_000}, content_type="application/json")
        self.assertEqual(400, response.status_code)

        # only known settings keys are accepted
        response = self.client.post(settings_url, {"theme": "dark"}, content_type="application/json")
        self.assertEqual(400, response.status_code)

        # posted keys are merged into existing settings
        response = self.client.post(
            settings_url, {"contact_cards": {"order": ["card-fields"]}}, content_type="application/json"
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual({"contact_cards": {"order": ["card-fields"]}}, response.json()["settings"])

        self.admin.refresh_from_db()
        self.assertEqual({"contact_cards": {"order": ["card-fields"]}}, self.admin.settings)

        # posting a key again replaces its value, leaving other stored keys alone
        self.admin.settings["other"] = {"kept": True}
        self.admin.save(update_fields=("settings",))

        self.client.post(
            settings_url, {"contact_cards": {"collapsed": ["card-nextup"]}}, content_type="application/json"
        )
        self.admin.refresh_from_db()
        self.assertEqual(
            {"contact_cards": {"collapsed": ["card-nextup"]}, "other": {"kept": True}}, self.admin.settings
        )

from zoneinfo import ZoneInfo

from temba.tests import TembaTest
from temba.utils.timezones import TimeZoneFormField, country_timezones, timezone_to_country_code


class TimezonesTest(TembaTest):
    def test_field(self):
        field = TimeZoneFormField(help_text="Test field")

        self.assertEqual(field.choices[0], ("Pacific/Midway", "(GMT-1100) Pacific/Midway"))
        self.assertEqual(field.coerce("Africa/Kigali"), ZoneInfo("Africa/Kigali"))

        # canonical zone names and UTC are offered as choices, legacy aliases are not
        tz_names = {c[0] for c in field.choices}
        self.assertIn("America/Los_Angeles", tz_names)
        self.assertIn("UTC", tz_names)
        self.assertNotIn("US/Pacific", tz_names)
        self.assertNotIn("GMT", tz_names)

    def test_timezone_country_code(self):
        self.assertEqual("RW", timezone_to_country_code(ZoneInfo("Africa/Kigali")))
        self.assertEqual("US", timezone_to_country_code(ZoneInfo("America/Chicago")))
        self.assertEqual("US", timezone_to_country_code(ZoneInfo("US/Pacific")))

        # GMT and UTC give empty
        self.assertEqual("", timezone_to_country_code(ZoneInfo("GMT")))
        self.assertEqual("", timezone_to_country_code(ZoneInfo("UTC")))

    def test_country_timezones(self):
        self.assertEqual(["Africa/Kigali"], country_timezones("RW"))
        self.assertIn("America/Chicago", country_timezones("US"))
        self.assertIn("US/Pacific", country_timezones("US"))
        self.assertEqual([], country_timezones("XX"))

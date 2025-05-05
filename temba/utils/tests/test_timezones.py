from zoneinfo import ZoneInfo

from temba.tests import TembaTest
from temba.utils.timezones import TimeZoneFormField, timezone_to_country_code


class TimezonesTest(TembaTest):
    def test_field(self):
        field = TimeZoneFormField(help_text="Test field")

        self.assertEqual(field.choices[0], ("Pacific/Midway", "(GMT-1100) Pacific/Midway"))
        self.assertEqual(field.coerce("Africa/Kigali"), ZoneInfo("Africa/Kigali"))

    def test_timezone_country_code(self):
        self.assertEqual("RW", timezone_to_country_code(ZoneInfo("Africa/Kigali")))
        self.assertEqual("US", timezone_to_country_code(ZoneInfo("America/Chicago")))
        self.assertEqual("US", timezone_to_country_code(ZoneInfo("US/Pacific")))

        # GMT and UTC give empty
        self.assertEqual("", timezone_to_country_code(ZoneInfo("GMT")))
        self.assertEqual("", timezone_to_country_code(ZoneInfo("UTC")))

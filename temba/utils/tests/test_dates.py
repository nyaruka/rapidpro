import datetime
from datetime import date, timezone as tzone
from zoneinfo import ZoneInfo

from temba.tests import TembaTest
from temba.utils.dates import date_range, datetime_to_str, datetime_to_timestamp, timestamp_to_datetime


class DatesTest(TembaTest):
    def test_datetime_to_timestamp(self):
        d1 = datetime.datetime(2014, 1, 2, 3, 4, 5, microsecond=123_456, tzinfo=tzone.utc)
        self.assertEqual(datetime_to_timestamp(d1), 1_388_631_845_123_456)  # from http://unixtimestamp.50x.eu
        self.assertEqual(timestamp_to_datetime(1_388_631_845_123_456), d1)

        tz = ZoneInfo("Africa/Kigali")
        d2 = datetime.datetime(2014, 1, 2, 3, 4, 5, microsecond=123_456).replace(tzinfo=tz)
        self.assertEqual(datetime_to_timestamp(d2), 1_388_624_645_123_456)
        self.assertEqual(timestamp_to_datetime(1_388_624_645_123_456), d2.astimezone(tzone.utc))

    def test_datetime_to_str(self):
        tz = ZoneInfo("Africa/Kigali")
        d2 = datetime.datetime(2014, 1, 2, 3, 4, 5, 6).replace(tzinfo=tz)

        self.assertIsNone(datetime_to_str(None, "%Y-%m-%d %H:%M", tz=tz))
        self.assertEqual(datetime_to_str(d2, "%Y-%m-%d %H:%M", tz=tz), "2014-01-02 03:04")
        self.assertEqual(datetime_to_str(d2, "%Y/%m/%d %H:%M", tz=tzone.utc), "2014/01/02 01:04")
        self.assertEqual(datetime_to_str(date(2023, 8, 16), "%Y/%m/%d %H:%M", tz=tzone.utc), "2023/08/16 00:00")

    def test_date_range(self):
        self.assertEqual(
            [date(2015, 1, 29), date(2015, 1, 30), date(2015, 1, 31), date(2015, 2, 1)],
            list(date_range(date(2015, 1, 29), date(2015, 2, 2))),
        )
        self.assertEqual([], list(date_range(date(2015, 1, 29), date(2015, 1, 29))))

from django.test import TestCase

from temba.settings_common import IPRangeList


class IPRangeListTest(TestCase):
    def test_contains(self):
        ranges = IPRangeList("127.0.0.1", "192.168.0.10", "192.168.0.0/24", "0.0.0.0")

        # single addresses match themselves
        self.assertIn("127.0.0.1", ranges)
        self.assertIn("192.168.0.10", ranges)
        self.assertIn("0.0.0.0", ranges)
        self.assertNotIn("127.0.0.2", ranges)

        # network blocks match any address inside them
        self.assertIn("192.168.0.1", ranges)
        self.assertIn("192.168.0.255", ranges)
        self.assertNotIn("192.168.1.5", ranges)
        self.assertNotIn("8.8.8.8", ranges)
        self.assertNotIn("::1", ranges)

        # anything that isn't an address is simply not a member rather than an error
        self.assertNotIn("not-an-ip", ranges)
        self.assertNotIn("", ranges)
        self.assertNotIn(None, ranges)

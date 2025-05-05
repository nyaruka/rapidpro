from temba.tests import TembaTest
from temba.utils import countries


class CountriesTest(TembaTest):
    def test_from_tel(self):
        self.assertIsNone(countries.from_tel(""))
        self.assertIsNone(countries.from_tel("123"))
        self.assertEqual("EC", countries.from_tel("+593979123456"))
        self.assertEqual("US", countries.from_tel("+1 213 621 0002"))

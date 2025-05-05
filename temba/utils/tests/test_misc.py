from decimal import Decimal

from temba.tests import TembaTest
from temba.utils import format_number, get_nested_key, percentage, set_nested_key, str_to_bool
from temba.utils.text import clean_string, generate_secret, generate_token, slugify_with, truncate, unsnakify


class MiscTest(TembaTest):
    def test_str_to_bool(self):
        self.assertFalse(str_to_bool(None))
        self.assertFalse(str_to_bool(""))
        self.assertFalse(str_to_bool("x"))
        self.assertTrue(str_to_bool("Y"))
        self.assertTrue(str_to_bool("Yes"))
        self.assertTrue(str_to_bool("TRUE"))
        self.assertTrue(str_to_bool("1"))

    def test_format_decimal(self):
        self.assertEqual("", format_number(None))
        self.assertEqual("0", format_number(Decimal("0.0")))
        self.assertEqual("10", format_number(Decimal("10")))
        self.assertEqual("100", format_number(Decimal("100.0")))
        self.assertEqual("123", format_number(Decimal("123")))
        self.assertEqual("123", format_number(Decimal("123.0")))
        self.assertEqual("123.34", format_number(Decimal("123.34")))
        self.assertEqual("123.34", format_number(Decimal("123.3400000")))
        self.assertEqual("-123", format_number(Decimal("-123.0")))
        self.assertEqual("-12300", format_number(Decimal("-123E+2")))
        self.assertEqual("-12350", format_number(Decimal("-123.5E+2")))
        self.assertEqual("-1.235", format_number(Decimal("-123.5E-2")))
        self.assertEqual(
            "-1000000000000001467812345696542157800075344236445874615",
            format_number(Decimal("-1000000000000001467812345696542157800075344236445874615")),
        )
        self.assertEqual("", format_number(Decimal("NaN")))

    def test_slugify_with(self):
        self.assertEqual("foo_bar", slugify_with("foo bar"))
        self.assertEqual("foo$bar", slugify_with("foo bar", "$"))

    def test_truncate(self):
        self.assertEqual("abc", truncate("abc", 5))
        self.assertEqual("abcde", truncate("abcde", 5))
        self.assertEqual("ab...", truncate("abcdef", 5))

    def test_unsnakify(self):
        self.assertEqual("", unsnakify(""))
        self.assertEqual("Org Name", unsnakify("org_name"))

    def test_generate_secret(self):
        rs = generate_secret(1000)
        self.assertEqual(1000, len(rs))
        self.assertFalse("1" in rs or "I" in rs or "0" in rs or "O" in rs)

    def test_percentage(self):
        self.assertEqual(0, percentage(0, 100))
        self.assertEqual(0, percentage(0, 0))
        self.assertEqual(0, percentage(100, 0))
        self.assertEqual(75, percentage(75, 100))
        self.assertEqual(76, percentage(759, 1000))

    def test_remove_control_charaters(self):
        self.assertIsNone(clean_string(None))
        self.assertEqual(clean_string("ngert\x07in."), "ngertin.")
        self.assertEqual(clean_string("Norbért"), "Norbért")

    def test_replace_non_characters(self):
        self.assertEqual(clean_string("Bangsa\ufddfBangsa"), "Bangsa\ufffdBangsa")

    def test_generate_token(self):
        self.assertEqual(len(generate_token()), 8)

    def test_nested_keys(self):
        nested = {}

        # set nested keys
        set_nested_key(nested, "favorites.beer", "Turbo King")
        self.assertEqual(nested, {"favorites": {"beer": "Turbo King"}})

        # get nested keys
        self.assertEqual("Turbo King", get_nested_key(nested, "favorites.beer"))
        self.assertEqual("", get_nested_key(nested, "favorites.missing"))
        self.assertEqual(None, get_nested_key(nested, "favorites.missing", None))

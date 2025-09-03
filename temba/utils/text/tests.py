from temba.tests import TembaTest
from temba.utils.text import clean_string, generate_secret, generate_token, slugify_with, truncate, unsnakify


class TextTest(TembaTest):
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

    def test_remove_control_charaters(self):
        self.assertIsNone(clean_string(None))
        self.assertEqual(clean_string("ngert\x07in."), "ngertin.")
        self.assertEqual(clean_string("Norbért"), "Norbért")

    def test_replace_non_characters(self):
        self.assertEqual(clean_string("Bangsa\ufddfBangsa"), "Bangsa\ufffdBangsa")

    def test_generate_token(self):
        self.assertEqual(len(generate_token()), 8)

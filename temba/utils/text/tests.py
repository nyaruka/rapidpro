from temba.tests import TembaTest
from temba.utils.text import clean_string, generate_secret, generate_token, obfuscate, slugify_with, truncate, unsnakify


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


class ObfuscateTest(TembaTest):
    def test_ids(self):
        key = (0xA3B1C, 0xD2E3F, 0x1A2B3, 0xC0FFEE)
        cases = [
            (1, "E2E6MX"),
            (2, "3MWB69"),
            (3, "Q3GP9G"),
            (4, "U6Y6T5"),
            (5, "SJPWLU"),
            (12345, "A6YWQL"),
            (999_999_999, "KNGEUX"),
            (1_073_741_823, "NVQ26R"),
            (1_073_741_824, "GQENS3N"),
            (1_073_741_825, "NTA3479"),
            (1_073_741_826, "KYEKD42"),
            (9_999_999_999, "P7U8B2J"),
        ]
        for id, expected_code in cases:
            actual_code = obfuscate.encode_id(id, key)
            self.assertEqual(expected_code, actual_code, f"encoding mismatch for id {id}")

            decoded = obfuscate.decode_id(expected_code, key)
            self.assertEqual(id, decoded, f"decoding mismatch for code {expected_code}")

        with self.assertRaises(ValueError):
            obfuscate.decode_id("E2E6MXXX", key)  # too long
        with self.assertRaises(ValueError):
            obfuscate.decode_id("E2E6M", key)  # too short
        with self.assertRaises(ValueError):
            obfuscate.decode_id("E2E6M0", key)  # invalid char 0

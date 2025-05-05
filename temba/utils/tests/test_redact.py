from django.test import TestCase

from temba.utils import redact


class RedactTest(TestCase):
    def test_variations(self):
        # phone number variations
        self.assertEqual(
            redact._variations("+593979099111"),
            [
                "%2B593979099111",
                "0593979099111",
                "+593979099111",
                "593979099111",
                "93979099111",
                "3979099111",
                "979099111",
                "79099111",
                "9099111",
            ],
        )

        # reserved XML/HTML characters escaped and unescaped
        self.assertEqual(
            redact._variations("<?&>"),
            [
                "0&lt;?&amp;&gt;",
                "+&lt;?&amp;&gt;",
                "%2B%3C%3F%26%3E",
                "&lt;?&amp;&gt;",
                "0%3C%3F%26%3E",
                "%3C%3F%26%3E",
                "0<?&>",
                "+<?&>",
                "<?&>",
            ],
        )

        # reserved JSON characters escaped and unescaped
        self.assertEqual(
            redact._variations("\n\r\t😄"),
            [
                "%2B%0A%0D%09%F0%9F%98%84",
                "0%0A%0D%09%F0%9F%98%84",
                "%0A%0D%09%F0%9F%98%84",
                "0\\n\\r\\t\\ud83d\\ude04",
                "+\\n\\r\\t\\ud83d\\ude04",
                "\\n\\r\\t\\ud83d\\ude04",
                "0\n\r\t😄",
                "+\n\r\t😄",
                "\n\r\t😄",
            ],
        )

    def test_text(self):
        # no match returns original and false
        self.assertEqual(redact.text("this is <+private>", "<public>", "********"), "this is <+private>")
        self.assertEqual(redact.text("this is 0123456789", "9876543210", "********"), "this is 0123456789")

        # text contains un-encoded raw value to be redacted
        self.assertEqual(redact.text("this is <+private>", "<+private>", "********"), "this is ********")

        # text contains URL encoded version of the value to be redacted
        self.assertEqual(redact.text("this is %2Bprivate", "+private", "********"), "this is ********")

        # text contains JSON encoded version of the value to be redacted
        self.assertEqual(redact.text('this is "+private"', "+private", "********"), 'this is "********"')

        # text contains XML encoded version of the value to be redacted
        self.assertEqual(redact.text("this is &lt;+private&gt;", "<+private>", "********"), "this is ********")

        # test matching the value partially
        self.assertEqual(redact.text("this is 123456789", "+123456789", "********"), "this is ********")

        self.assertEqual(redact.text("this is +123456789", "123456789", "********"), "this is ********")
        self.assertEqual(redact.text("this is 123456789", "0123456789", "********"), "this is ********")

        # '3456789' matches the input string
        self.assertEqual(redact.text("this is 03456789", "+123456789", "********"), "this is 0********")

        # only rightmost 7 chars of the test matches
        self.assertEqual(redact.text("this is 0123456789", "xxx3456789", "********"), "this is 012********")

        # all matches replaced
        self.assertEqual(
            redact.text('{"number_full": "+593979099111", "number_short": "0979099111"}', "+593979099111", "********"),
            '{"number_full": "********", "number_short": "0********"}',
        )

        # custom mask
        self.assertEqual(redact.text("this is private", "private", "🌼🌼🌼🌼"), "this is 🌼🌼🌼🌼")

    def test_http_trace(self):
        # not an HTTP trace
        self.assertEqual(redact.http_trace("hello", "12345", "********", ("name",)), "********")

        # a JSON body
        self.assertEqual(
            redact.http_trace(
                'POST /c/t/23524/receive HTTP/1.1\r\nHost: yy12345\r\n\r\n{"name": "Bob Smith", "number": "xx12345"}',
                "12345",
                "********",
                ("name",),
            ),
            'POST /c/t/23524/receive HTTP/1.1\r\nHost: yy********\r\n\r\n{"name": "********", "number": "xx********"}',
        )

        # a URL-encoded body
        self.assertEqual(
            redact.http_trace(
                "POST /c/t/23524/receive HTTP/1.1\r\nHost: yy12345\r\n\r\nnumber=xx12345&name=Bob+Smith",
                "12345",
                "********",
                ("name",),
            ),
            "POST /c/t/23524/receive HTTP/1.1\r\nHost: yy********\r\n\r\nnumber=xx********&name=********",
        )

        # a body with neither encoding redacted as text if body keys not provided
        self.assertEqual(
            redact.http_trace(
                "POST /c/t/23524/receive HTTP/1.1\r\nHost: yy12345\r\n\r\n//xx12345//", "12345", "********"
            ),
            "POST /c/t/23524/receive HTTP/1.1\r\nHost: yy********\r\n\r\n//xx********//",
        )

        # a body with neither encoding returned as is if body keys provided but we couldn't parse the body
        self.assertEqual(
            redact.http_trace(
                "POST /c/t/23524/receive HTTP/1.1\r\nHost: yy12345\r\n\r\n//xx12345//", "12345", "********", ("name",)
            ),
            "POST /c/t/23524/receive HTTP/1.1\r\nHost: yy********\r\n\r\n********",
        )

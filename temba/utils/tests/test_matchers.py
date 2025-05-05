from temba.tests import TembaTest, matchers


class MatchersTest(TembaTest):
    def test_string(self):
        self.assertEqual("abc", matchers.String())
        self.assertEqual("", matchers.String())
        self.assertNotEqual(None, matchers.String())
        self.assertNotEqual(123, matchers.String())

        self.assertEqual("abc", matchers.String(pattern=r"\w{3}$"))
        self.assertNotEqual("ab", matchers.String(pattern=r"\w{3}$"))
        self.assertNotEqual("abcd", matchers.String(pattern=r"\w{3}$"))

    def test_isodate(self):
        self.assertEqual("2013-02-01T07:08:09.100000+04:30", matchers.ISODatetime())
        self.assertEqual("2018-02-21T20:34:07.198537686Z", matchers.ISODatetime())
        self.assertEqual("2018-02-21T20:34:07.19853768Z", matchers.ISODatetime())
        self.assertEqual("2018-02-21T20:34:07.198Z", matchers.ISODatetime())
        self.assertEqual("2018-02-21T20:34:07Z", matchers.ISODatetime())
        self.assertEqual("2013-02-01T07:08:09.100000Z", matchers.ISODatetime())
        self.assertNotEqual(None, matchers.ISODatetime())
        self.assertNotEqual("abc", matchers.ISODatetime())

    def test_uuid4string(self):
        self.assertEqual("85ECBE45-E2DF-4785-8FC8-16FA941E0A79", matchers.UUID4String())
        self.assertEqual("85ecbe45-e2df-4785-8fc8-16fa941e0a79", matchers.UUID4String())
        self.assertNotEqual(None, matchers.UUID4String())
        self.assertNotEqual("abc", matchers.UUID4String())

    def test_dict(self):
        self.assertEqual({}, matchers.Dict())
        self.assertEqual({"a": "b"}, matchers.Dict())
        self.assertNotEqual(None, matchers.Dict())
        self.assertNotEqual([], matchers.Dict())

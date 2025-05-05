from collections import OrderedDict
from datetime import datetime, timezone as tzone
from decimal import Decimal

from django.utils import timezone

from temba.tests import TembaTest
from temba.utils import json


class EncoderTest(TembaTest):
    def test_encode_decode(self):
        # create a time that has a set millisecond
        now = timezone.now().replace(microsecond=1000)

        # our dictionary to encode
        source = dict(name="Date Test", age=Decimal("10"), now=now)

        # encode it
        encoded = json.dumps(source)

        self.assertEqual(
            json.loads(encoded), {"name": "Date Test", "age": Decimal("10"), "now": json.encode_datetime(now)}
        )

        # try it with a microsecond of 0 instead
        source["now"] = timezone.now().replace(microsecond=0)

        # encode it
        encoded = json.dumps(source)

        # test that we throw with unknown types
        with self.assertRaises(TypeError):
            json.dumps(dict(foo=Exception("invalid")))

    def test_json(self):
        self.assertEqual(OrderedDict({"one": 1, "two": Decimal("0.2")}), json.loads('{"one": 1, "two": 0.2}'))
        self.assertEqual(
            '{"dt": "2018-08-27T20:41:28.123Z"}',
            json.dumps({"dt": datetime(2018, 8, 27, 20, 41, 28, 123000, tzinfo=tzone.utc)}),
        )

from unittest.mock import patch

from django_valkey import get_valkey_connection

from django.utils import timezone

from temba.api.support import record_deprecated
from temba.tests import TembaTest
from temba.tests.base import cleanup


class RecordDeprecatedTest(TembaTest):
    @cleanup(valkey=True)
    def test_record(self):
        r = get_valkey_connection()
        key = f"warnings:{timezone.now():%Y-%m}"
        r.delete(key)  # other tests may have recorded into this month's bucket

        record_deprecated(self.org, "messages#filter:id")
        record_deprecated(self.org, "messages#filter:id")
        record_deprecated(self.org, "definitions#get")
        record_deprecated(self.org2, "messages#filter:id")

        self.assertEqual(
            {
                f"api:deprecated:{self.org.id}/messages#filter:id": b"2",
                f"api:deprecated:{self.org.id}/definitions#get": b"1",
                f"api:deprecated:{self.org2.id}/messages#filter:id": b"1",
            },
            {f.decode(): c for f, c in r.hgetall(key).items()},
        )

        # bucket expires so that we're not accumulating this forever
        self.assertEqual(90 * 24 * 60 * 60, r.ttl(key))

    def test_record_error_is_not_fatal(self):
        with patch("temba.api.support.get_valkey_connection") as mock_get_conn:
            mock_get_conn.side_effect = ValueError("boom")

            record_deprecated(self.org, "messages#filter:id")  # no exception

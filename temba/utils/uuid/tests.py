from datetime import datetime, timezone as tzone

from temba.tests.base import TembaTest

from . import find_uuid, is_uuid, is_uuid7, uuid4, uuid7


class UUIDTest(TembaTest):
    def test_is_uuid(self):
        self.assertFalse(is_uuid(None))
        self.assertFalse(is_uuid(""))
        self.assertFalse(is_uuid("1234567890-xx"))
        self.assertTrue(is_uuid("d749e4e9-2898-4e47-9418-7a89d9e51359"))
        self.assertFalse(is_uuid("http://d749e4e9-2898-4e47-9418-7a89d9e51359/"))

    def test_find_uuid(self):
        self.assertEqual(None, find_uuid(""))
        self.assertEqual(None, find_uuid("xx"))
        self.assertEqual("d749e4e9-2898-4e47-9418-7a89d9e51359", find_uuid("d749e4e9-2898-4e47-9418-7a89d9e51359"))
        self.assertEqual(
            "d749e4e9-2898-4e47-9418-7a89d9e51359", find_uuid("http://d749e4e9-2898-4e47-9418-7a89d9e51359/")
        )

    def test_uuid7(self):
        last = None
        for _ in range(100):
            u = uuid7()
            self.assertTrue(is_uuid7(u))
            if last:
                self.assertGreater(u, last)
            last = u

        u3 = uuid7(when=datetime(2025, 8, 11, 20, 36, 41, 114764, tzinfo=tzone.utc))
        u4 = uuid7(when=datetime(2025, 8, 11, 20, 36, 41, 116000, tzinfo=tzone.utc))
        self.assertTrue(is_uuid7(u3))
        self.assertTrue(is_uuid7(u4))
        self.assertLess(u3, u4)
        self.assertTrue(u3.startswith("01989ad9-7c1a-7"))  # go code gives ~ 01989ad9-7c1a-7b8d-a59e-141c265730dc

        self.assertFalse(is_uuid7(uuid4()))

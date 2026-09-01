from datetime import datetime, timedelta, timezone as tzone

from temba.tests import TembaTest
from temba.utils import uuid


class TestUUIDs(TembaTest):
    def test_seeded_generator(self):
        g = uuid.seeded_generator(123)
        self.assertEqual(uuid.UUID("66b3670d-b37d-4644-aedd-51167c53dac4", version=4), g())
        self.assertEqual(uuid.UUID("07ff4068-f3de-4c44-8a3e-921b952aa8d6", version=4), g())

        # same seed, same UUIDs
        g = uuid.seeded_generator(123)
        self.assertEqual(uuid.UUID("66b3670d-b37d-4644-aedd-51167c53dac4", version=4), g())
        self.assertEqual(uuid.UUID("07ff4068-f3de-4c44-8a3e-921b952aa8d6", version=4), g())

        # different seed, different UUIDs
        g = uuid.seeded_generator(456)
        self.assertEqual(uuid.UUID("8c338abf-94e2-4c73-9944-72f7a6ff5877", version=4), g())
        self.assertEqual(uuid.UUID("c8e0696f-b3f6-4e63-a03a-57cb95bdb6e3", version=4), g())

    def test_uuid7_range(self):
        when = datetime(2026, 9, 1, 12, 30, 45, 123456, tzinfo=tzone.utc)
        lowest, highest = uuid.uuid7_range(when)

        self.assertEqual(7, lowest.version)
        self.assertEqual(7, highest.version)
        self.assertEqual("01a05cf3-5183-7000-8000-000000000000", str(lowest))
        self.assertEqual("01a05cf3-5183-7fff-bfff-ffffffffffff", str(highest))

        # bounds cover any uuid generated in that millisecond regardless of the sub-millisecond part of the time
        for offset in (timedelta(), timedelta(microseconds=-456), timedelta(microseconds=543)):
            generated = uuid.uuid7(when + offset)
            self.assertTrue(lowest <= generated <= highest, offset)

        # but not the neighboring milliseconds
        self.assertLess(uuid.uuid7(when - timedelta(milliseconds=1)), lowest)
        self.assertGreater(uuid.uuid7(when + timedelta(milliseconds=1)), highest)

    def test_uuid7(self):
        when = datetime(2026, 9, 1, 12, 30, 45, 123456, tzinfo=tzone.utc)

        # uuids generated for the same millisecond are ordered as generated, as are ones generated for now
        for_when = [uuid.uuid7(when) for _ in range(5)]
        for_now = [uuid.uuid7() for _ in range(5)]
        self.assertEqual(sorted(for_when), for_when)
        self.assertEqual(sorted(for_now), for_now)
        self.assertEqual(5, len(set(for_when)))
        self.assertTrue(all(u.version == 7 for u in for_when + for_now))

        # and are within the bounds for that millisecond
        lowest, highest = uuid.uuid7_range(when)
        self.assertTrue(all(lowest <= u <= highest for u in for_when))

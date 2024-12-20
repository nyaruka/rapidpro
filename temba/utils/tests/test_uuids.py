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

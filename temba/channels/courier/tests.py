from django_redis import get_redis_connection

from temba.tests.base import TembaTest

from . import QueuedChannel


class CourierTest(TembaTest):
    def test_queued_channel(self):
        ch = self.create_channel("NX", "Vonage", "+1234567890")
        qch = QueuedChannel.from_channel(ch)

        self.assertEqual(str(ch.uuid), qch.uuid)
        self.assertEqual(10, qch.tps)
        self.assertEqual(f"msgs:{ch.uuid}|10/1", qch.high_queue_key)
        self.assertEqual(f"msgs:{ch.uuid}|10/0", qch.bulk_queue_key)

        r = get_redis_connection()
        r.zadd(qch.high_queue_key, {'{"text":"1"}': 10001, '{"text":"2"}': 10002})
        r.zadd(qch.bulk_queue_key, {'{"text":"3"}': 10003})

        self.assertEqual(3, ch.get_queue_size(r))

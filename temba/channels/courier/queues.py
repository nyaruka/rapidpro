from dataclasses import dataclass

import regex

QUEUESET_ACTIVE = "msgs:active"
QUEUESET_THROTTLED = "msgs:throttled"

QUEUE_PATTERN = regex.compile(r"msgs:(?P<uuid>[a-z0-9\-]{36})\|(?P<tps>\d+)")

DEFAULT_TPS = 10


@dataclass
class QueuedChannel:
    uuid: str
    tps: int
    high_queue_key: str
    bulk_queue_key: str

    @classmethod
    def from_channel(cls, ch):
        tps = ch.tps or DEFAULT_TPS
        return QueuedChannel(str(ch.uuid), tps, f"msgs:{ch.uuid}|{tps}/1", f"msgs:{ch.uuid}|{tps}/0")

    def get_queue_sizes(self, r) -> tuple:
        """
        Returns a tuple of the size of the priority and bulk queues
        """
        return r.zcard(self.high_queue_key), r.zcard(self.bulk_queue_key)


def get_queued_channels(r, queueset: str) -> list:
    """
    Returns list of tuples of queued channels and number of workers
    """
    channels = []

    for ch_key, workers in r.zrange(queueset, 0, -1, withscores=True):
        ch_key = ch_key.decode()
        match = QUEUE_PATTERN.match(ch_key)
        uuid, tps = match.group("uuid"), match.group("tps")
        channels.append((QueuedChannel(uuid, tps, f"{ch_key}/1", f"{ch_key}/0"), int(workers)))

    return channels

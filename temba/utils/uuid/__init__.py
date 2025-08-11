import os
import random
import re
import sys
import time
from uuid import UUID, uuid4 as real_uuid4

default_generator = real_uuid4

UUID_REGEX = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def uuid4() -> UUID:
    return default_generator()


def seeded_generator(seed: int):
    """
    Returns a UUID v4 generation function which is backed by a RNG with the given seed
    """
    rng = random.Random(seed)

    def generator() -> UUID:
        data = []
        for i in range(4):
            integer = rng.getrandbits(4 * 8)
            data.extend(integer.to_bytes(4, sys.byteorder))
        return UUID(bytes=bytes(data), version=4)

    return generator


def is_uuid(val: str) -> bool:
    """
    Returns whether the given string is a valid UUID
    """
    try:
        UUID(str(val))
        return True
    except Exception:
        return False


def find_uuid(val: str) -> str | None:
    """
    Finds and returns the first valid UUID in the given string
    """
    match = UUID_REGEX.search(val)
    return match.group(0) if match else None


def is_uuid7(val: str) -> bool:
    as_str = str(val)
    return len(as_str) == 36 and as_str[14] == "7"


# UUID v7 code below is taken from CPython source which will be available in Python 3.14, but modified as follows...
#
#  - to return the UUID as a string because the standard UUID class does not support v7 yet.
#  - to take an optional `when` argument to allow generating a UUID for a specific time.
#
# See https://github.com/python/cpython/blob/362692852f13cdd1d33cc7ed35c0cbac7af1a785/Lib/uuid.py#L110


_last_timestamp_v7 = None
_last_counter_v7 = 0  # 42-bit counter
_RFC_4122_VERSION_7_FLAGS = (7 << 76) | (0x8000 << 48)


def _uuid7_get_counter_and_tail():
    rand = int.from_bytes(os.urandom(10))
    # 42-bit counter with MSB set to 0
    counter = (rand >> 32) & 0x1FF_FFFF_FFFF
    # 32-bit random data
    tail = rand & 0xFFFF_FFFF
    return counter, tail


def uuid7(when=None) -> str:
    """Generate a UUID from a Unix timestamp in milliseconds and random bits.

    UUIDv7 objects feature monotonicity within a millisecond.
    """
    # --- 48 ---   -- 4 --   --- 12 ---   -- 2 --   --- 30 ---   - 32 -
    # unix_ts_ms | version | counter_hi | variant | counter_lo | random
    #
    # 'counter = counter_hi | counter_lo' is a 42-bit counter constructed
    # with Method 1 of RFC 9562, §6.2, and its MSB is set to 0.
    #
    # 'random' is a 32-bit random value regenerated for every new UUID.
    #
    # If multiple UUIDs are generated within the same millisecond, the LSB
    # of 'counter' is incremented by 1. When overflowing, the timestamp is
    # advanced and the counter is reset to a random 42-bit integer with MSB
    # set to 0.

    global _last_timestamp_v7
    global _last_counter_v7

    if when:
        timestamp_ms = int(when.timestamp() * 1000)
        counter, tail = _uuid7_get_counter_and_tail()
    else:
        nanoseconds = time.time_ns()
        timestamp_ms = nanoseconds // 1_000_000

        if _last_timestamp_v7 is None or timestamp_ms > _last_timestamp_v7:
            counter, tail = _uuid7_get_counter_and_tail()
        else:  # pragma: no cover
            if timestamp_ms < _last_timestamp_v7:
                timestamp_ms = _last_timestamp_v7 + 1
            # advance the 42-bit counter
            counter = _last_counter_v7 + 1
            if counter > 0x3FF_FFFF_FFFF:
                # advance the 48-bit timestamp
                timestamp_ms += 1
                counter, tail = _uuid7_get_counter_and_tail()
            else:
                # 32-bit random data
                tail = int.from_bytes(os.urandom(4))

    unix_ts_ms = timestamp_ms & 0xFFFF_FFFF_FFFF
    counter_msbs = counter >> 30
    # keep 12 counter's MSBs and clear variant bits
    counter_hi = counter_msbs & 0x0FFF
    # keep 30 counter's LSBs and clear version bits
    counter_lo = counter & 0x3FFF_FFFF
    # ensure that the tail is always a 32-bit integer (by construction,
    # it is already the case, but future interfaces may allow the user
    # to specify the random tail)
    tail &= 0xFFFF_FFFF

    int_uuid_7 = unix_ts_ms << 80
    int_uuid_7 |= counter_hi << 64
    int_uuid_7 |= counter_lo << 32
    int_uuid_7 |= tail
    # by construction, the variant and version bits are already cleared
    int_uuid_7 |= _RFC_4122_VERSION_7_FLAGS

    # defer global update until all computations are done
    _last_timestamp_v7 = timestamp_ms
    _last_counter_v7 = counter

    # return as string because we still can't create a v7 uuid.UUID instance
    hex = "%032x" % int_uuid_7
    return f"{hex[:8]}-{hex[8:12]}-{hex[12:16]}-{hex[16:20]}-{hex[20:]}"

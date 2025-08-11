import random
import re
import sys
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


def uuid7(when=None) -> str:
    """
    Until standard library gets v7 support in 3.14 we lean on https://github.com/aminalaee/uuid-utils which uses the
    standard Rust library. Note also that it returns a str rather than a UUID instance because the latter doesn't accept
    7 as a version number.
    """

    import uuid_utils as uuid

    if when:
        seconds = int(when.timestamp())
        nanos = int(when.microsecond * 1000)
        return str(uuid.uuid7(seconds, nanos))

    return str(uuid.uuid7())


def is_uuid7(val: str) -> bool:
    return len(str(val)) == 36 and str(val)[14] == "7"

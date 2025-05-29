import json
import zlib

from boto3.dynamodb.types import Binary


def load_jsongz(data: Binary | bytes) -> dict:
    """
    Loads a value from gzipped JSON
    """
    return json.loads(zlib.decompress(bytes(data), wbits=zlib.MAX_WBITS | 16))


def dump_jsongz(value: dict) -> bytes:
    """
    Dumps a value to gzipped JSON
    """
    return zlib.compress(json.dumps(value).encode("utf-8"), wbits=zlib.MAX_WBITS | 16)

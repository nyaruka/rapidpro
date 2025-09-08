# Safe uppercase alphabet, base-32 (no I, O, 0, 1)
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ALPHABET_BASE = len(ALPHABET)  # 32

# Threshold where we switch from 6 → 7 chars
THRESHOLD_6CHARS = ALPHABET_BASE**6  # 1,073,741,824

MAX_ID = 9_999_999_999

F30_BIT_SIZE = 30
F30_HALF_SIZE = F30_BIT_SIZE // 2  # 15 bits
F30_MASK = (1 << F30_HALF_SIZE) - 1  # 0x7FFF

F34_BIT_SIZE = 34
F34_HALF_SIZE = F34_BIT_SIZE // 2  # 17 bits
F34_MASK = (1 << F34_HALF_SIZE) - 1  # 0x1FFFF


def encode_id(id_: int, key: tuple) -> str:
    assert 0 < id_ <= MAX_ID, "encode requires id between 1 and 9,999,999,999"
    assert len(key) == 4, "key must be a tuple of 4 integers"

    if id_ < THRESHOLD_6CHARS:
        obfuscated = _feistel30_encrypt(id_, key)
        code_length = 6
    else:
        # For larger IDs, use 7 characters with extended Feistel for more bits
        # Map the ID to a range that fits in 7 characters (BASE^7)
        # We have BASE^7 = 32^7 = 34,359,738,368 possible values

        # Normalize to range [0, BASE^7 - THRESHOLD_6CHARS)
        normalized_id = id_ - THRESHOLD_6CHARS

        # Use extended Feistel cipher for larger bit space
        obfuscated = _feistel34_encrypt(normalized_id, key)
        code_length = 7

    chars = []
    for _ in range(code_length):
        chars.append(ALPHABET[obfuscated % ALPHABET_BASE])
        obfuscated //= ALPHABET_BASE
    return "".join(reversed(chars))


def decode_id(code: str, key: tuple) -> int:
    code = code.upper()
    num = 0
    for c in code:
        try:
            idx = ALPHABET.index(c)
        except ValueError:
            raise ValueError(f"Invalid character '{c}' in code")
        num = num * ALPHABET_BASE + idx

    if len(code) == 6:
        return _feistel30_decrypt(num, key)
    elif len(code) == 7:
        normalized_id = _feistel34_decrypt(num, key)
        return normalized_id + THRESHOLD_6CHARS
    else:
        raise ValueError("Code must be 6 or 7 characters")


def _feistel30_encrypt(n: int, key: tuple) -> int:
    left = (n >> F30_HALF_SIZE) & F30_MASK
    right = n & F30_MASK

    for k in key:
        new_left = right
        right = left ^ (_feistel_round(right, k, F30_MASK) & F30_MASK)
        left = new_left

    return (left << F30_HALF_SIZE) | right


def _feistel30_decrypt(n: int, key: tuple) -> int:
    left = (n >> F30_HALF_SIZE) & F30_MASK
    right = n & F30_MASK

    for k in reversed(key):
        new_right = left
        left = right ^ (_feistel_round(left, k, F30_MASK) & F30_MASK)
        right = new_right

    return (left << F30_HALF_SIZE) | right


def _feistel34_encrypt(n: int, key: tuple) -> int:
    left = (n >> F34_HALF_SIZE) & F34_MASK
    right = n & F34_MASK

    for k in key:
        new_left = right
        right = left ^ (_feistel_round(right, k, F34_MASK) & F34_MASK)
        left = new_left

    return (left << F34_HALF_SIZE) | right


def _feistel34_decrypt(n: int, key: tuple) -> int:
    left = (n >> F34_HALF_SIZE) & F34_MASK
    right = n & F34_MASK

    for k in reversed(key):
        new_right = left
        left = right ^ (_feistel_round(left, k, F34_MASK) & F34_MASK)
        right = new_right

    return (left << F34_HALF_SIZE) | right


def _feistel_round(r: int, k: int, mask: int) -> int:
    r = (r ^ k) * 0x45D9F3B
    r ^= r >> 16
    return r & mask

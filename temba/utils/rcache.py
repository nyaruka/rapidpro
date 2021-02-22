from datetime import timedelta

from django.utils import timezone

KEY_PATTERN = "%s:%s"
DATE_PATTERN = "%Y_%m_%d"
SECONDS_IN_A_DAY = 60 * 60 * 24


def get(redis_conn, group, key):
    now = timezone.now()
    yesterday = now - timedelta(hours=24)

    today_key = KEY_PATTERN % (group, now.strftime(DATE_PATTERN))
    yesterday_key = KEY_PATTERN % (group, yesterday.strftime(DATE_PATTERN))

    value = redis_conn.hget(today_key, key)
    if value is not None:
        return str(value, "utf-8")
    value = redis_conn.hget(yesterday_key, key)
    if value is not None:  # pragma: no cover
        return str(value, "utf-8")
    return value


def set(redis_conn, group, key, value):
    now = timezone.now()
    date_key = KEY_PATTERN % (group, now.strftime(DATE_PATTERN))
    redis_conn.hset(date_key, key, value)
    redis_conn.expire(date_key, SECONDS_IN_A_DAY)


def delete(redis_conn, group, key):
    now = timezone.now()
    yesterday = now - timedelta(hours=24)

    today_key = KEY_PATTERN % (group, now.strftime(DATE_PATTERN))
    yesterday_key = KEY_PATTERN % (group, yesterday.strftime(DATE_PATTERN))

    redis_conn.hdel(today_key, key)
    redis_conn.hdel(yesterday_key, key)


def clear(redis_conn, group):
    now = timezone.now()
    yesterday = now - timedelta(hours=24)

    today_key = KEY_PATTERN % (group, now.strftime(DATE_PATTERN))
    yesterday_key = KEY_PATTERN % (group, yesterday.strftime(DATE_PATTERN))

    redis_conn.delete(today_key)
    redis_conn.delete(yesterday_key)

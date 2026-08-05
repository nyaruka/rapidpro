# parallel test workers import this module before django.setup() runs, so it can't import (or live in a package
# that imports) anything requiring the app registry, e.g. models or temba.tests

import io
import re

import django.test.runner
from django.conf import settings
from django.core.files.storage import storages
from django.core.management import call_command
from django.test.runner import DiscoverRunner, ParallelTestSuite, _init_worker


def _temba_init_worker(counter, *args, **kwargs):
    """
    Django's own worker init gives each parallel test worker its own clone of the test database. This extends that
    with a per-worker valkey database and per-worker DynamoDB tables and S3 buckets in localstack, so that workers
    can't see each other's state in those services.
    """

    _init_worker(counter, *args, **kwargs)

    worker_id = django.test.runner._worker_id

    # serial test runs use valkey database 10 and local dev uses 15, so give workers 1..10 databases 0..9
    if worker_id > 10:
        raise RuntimeError("can't run more than 10 parallel test workers as each needs its own valkey database")

    caches = settings.CACHES["default"]
    caches["LOCATION"] = re.sub(r"/\d+$", f"/{worker_id - 1}", caches["LOCATION"])

    settings.DYNAMO_TABLE_PREFIX = f"Test{worker_id}"
    settings.BUCKET_PREFIX = f"test{worker_id}"

    for alias, config in settings.STORAGES.items():
        bucket_name = config.get("OPTIONS", {}).get("bucket_name")
        if bucket_name:
            new_name = bucket_name.replace("test-", f"{settings.BUCKET_PREFIX}-", 1)
            config["OPTIONS"]["bucket_name"] = new_name

            # some storage backends are instantiated during django.setup() above (e.g. model field storages) so
            # existing instances need to be updated as well
            storage = storages[alias]
            storage.bucket_name = new_name
            storage.__dict__.pop("bucket", None)

    settings.STORAGE_URL = f"{settings.AWS_S3_ENDPOINT_URL}/{settings.BUCKET_PREFIX}-default"

    # create this worker's tables and buckets if they don't already exist (both commands read the prefixes set above)
    call_command("migrate_dynamo", stdout=io.StringIO())
    call_command("create_buckets", stdout=io.StringIO())


class TembaParallelTestSuite(ParallelTestSuite):
    init_worker = _temba_init_worker


class TembaTestRunner(DiscoverRunner):
    parallel_test_suite = TembaParallelTestSuite

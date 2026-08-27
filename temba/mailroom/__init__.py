from django.conf import settings

from .client.exceptions import *  # noqa
from .client.types import *  # noqa


def get_client():
    from .client.client import MailroomClient

    # tests use a client which fakes endpoints against the test database, so that no test can reach a live mailroom
    if settings.TESTING:
        from temba.tests.mailroom import TestClient

        return TestClient()

    return MailroomClient(settings.MAILROOM_URL, settings.MAILROOM_AUTH_TOKEN)  # pragma: no cover

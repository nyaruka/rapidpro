from __future__ import print_function, unicode_literals

from celery.task import task
from temba.channels.models import Channel


@task(track_started=True, name='refresh_jiochat_access_tokens')
def refresh_jiochat_access_tokens():  # pragma: needs cover
    Channel.get_type_from_code('JC').refresh_access_token()

from __future__ import print_function, unicode_literals

from celery.task import task
from temba.channels.models import Channel


@task(track_started=True, name='refresh_wechat_access_tokens')
def refresh_wechat_access_tokens():  # pragma: needs cover
    Channel.refresh_access_token_for_code('WC')

import logging

from celery import shared_task

from temba.utils.crons import cron_task

from .models import BroadcastMsgCount, LabelCount, Media

logger = logging.getLogger(__name__)


@cron_task(lock_timeout=7200)
def squash_msg_counts():
    LabelCount.squash()
    BroadcastMsgCount.squash()


@shared_task
def process_media_upload(media_id):
    Media.objects.get(id=media_id).process_upload()

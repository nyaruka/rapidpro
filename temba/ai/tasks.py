from datetime import timedelta

from django.utils import timezone

from temba.utils.crons import cron_task
from temba.utils.models import delete_in_batches

from .models import LLMCount


@cron_task(lock_timeout=7200)
def squash_llm_counts():
    LLMCount.squash()


@cron_task()
def trim_llm_counts():
    trim_before = timezone.now().date() - timedelta(days=30)

    num_deleted = delete_in_batches(LLMCount.objects.filter(day__lt=trim_before))

    return {"deleted": num_deleted}

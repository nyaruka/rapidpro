import time
from enum import Enum

from django_valkey import get_valkey_connection

from django.utils import timezone

from temba.utils import json

DEFAULT_PRIORITY = 0


class BatchTask(Enum):
    IMPORT_CONTACT_BATCH = "import_contact_batch"


def queue_contact_import_batch(batch):
    """
    Queues a task to import a batch of contacts
    """

    task = {"contact_import_batch_id": batch.id}

    _queue_batch_task(batch.contact_import.org.id, BatchTask.IMPORT_CONTACT_BATCH, task, DEFAULT_PRIORITY)


def _queue_batch_task(org_id, task_type, task, priority):
    """
    Adds the passed in task to the mailroom batch queue
    """

    r = get_valkey_connection()
    pipe = r.pipeline()
    _queue_task(pipe, org_id, task_type, task, priority)
    pipe.execute()


def _queue_task(pipe, org_id, task_type, task, priority):
    """
    Queues a task to mailroom

    Args:
        pipe: an open valkey pipe
        org_id: the id of the org for this task
        queue: the queue the task should be added to
        task_type: the type of the task
        task: the task definition
        priority: the priority of this task

    """

    # our score is the time in milliseconds since epoch + any priority modifier
    score = int(round(time.time() * 1000)) + priority

    # create our payload
    payload = _create_mailroom_task(task_type, task)

    # push onto our org queue
    pipe.zadd(f"tasks:batch:{org_id}", {json.dumps(payload): score})

    # and mark that org as active
    pipe.zincrby("tasks:batch:active", 0, org_id)


def _create_mailroom_task(task_type, task):
    """
    Returns a mailroom format task job based on the task type and passed in task
    """
    return {"type": task_type.value, "task": task, "queued_on": timezone.now()}

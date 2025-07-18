import time
from enum import Enum

from django_valkey import get_valkey_connection

from django.utils import timezone

from temba.utils import json

HIGH_PRIORITY = -10000000
DEFAULT_PRIORITY = 0


class BatchTask(Enum):
    START_FLOW = "start_flow"
    INTERRUPT_SESSIONS = "interrupt_sessions"
    IMPORT_CONTACT_BATCH = "import_contact_batch"
    INTERRUPT_CHANNEL = "interrupt_channel"


def queue_flow_start(start):
    """
    Queues the passed in flow start for starting by mailroom
    """

    org_id = start.flow.org_id

    task = {
        "start_id": start.id,
        "start_type": start.start_type,
        "org_id": org_id,
        "created_by_id": start.created_by_id,
        "flow_id": start.flow_id,
        "contact_ids": list(start.contacts.values_list("id", flat=True)),
        "group_ids": list(start.groups.values_list("id", flat=True)),
        "urns": start.urns or [],
        "query": start.query,
        "exclusions": start.exclusions,
        "params": start.params,
    }

    _queue_batch_task(org_id, BatchTask.START_FLOW, task, HIGH_PRIORITY)


def queue_contact_import_batch(batch):
    """
    Queues a task to import a batch of contacts
    """

    task = {"contact_import_batch_id": batch.id}

    _queue_batch_task(batch.contact_import.org.id, BatchTask.IMPORT_CONTACT_BATCH, task, DEFAULT_PRIORITY)


def queue_interrupt_channel(org, channel):
    """
    Queues an interrupt channel task for handling by mailroom
    """

    task = {"channel_id": channel.id}

    _queue_batch_task(org.id, BatchTask.INTERRUPT_CHANNEL, task, HIGH_PRIORITY)


def queue_interrupt(org, *, contacts=None, flow=None):
    """
    Queues an interrupt task for handling by mailroom
    """

    assert contacts or flow, "must specify either a set of contacts or a flow"

    task = {}
    if contacts:
        task["contact_ids"] = [c.id for c in contacts]
    if flow:
        task["flow_ids"] = [flow.id]

    _queue_batch_task(org.id, BatchTask.INTERRUPT_SESSIONS, task, HIGH_PRIORITY)


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

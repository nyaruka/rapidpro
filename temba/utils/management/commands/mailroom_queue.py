from collections import defaultdict

from django_redis import get_redis_connection
from iso8601 import parse_date

from django.core.management import BaseCommand
from django.utils.timesince import timesince

from temba.flows.models import Flow
from temba.orgs.models import Org
from temba.utils import json


class Command(BaseCommand):
    help = "Dumps contents of mailroom's batch queue"

    def handle(self, *args, **kwargs):
        r = get_redis_connection()
        count_style = self.style.SQL_KEYWORD

        for org_id, workers in r.zrange("batch:active", 0, -1, withscores=True):
            org = Org.objects.get(id=int(org_id))
            org_queue = f"batch:{org.id}"
            org_task_count = r.zcard(org_queue)

            self.stdout.write(f"{count_style(org_task_count)} {org.name} ({int(workers)} workers)")

            tasks_by_type = defaultdict(list)
            oldest_by_type = {}

            for task_str in r.zrange(org_queue, 0, -1):
                task = json.loads(task_str.decode())
                task_type = task["type"]
                tasks_by_type[task_type].append(task)
                queued_on = parse_date(task["queued_on"])
                if task_type not in oldest_by_type or queued_on < oldest_by_type[task_type]:
                    oldest_by_type[task_type] = queued_on

            for task_type, tasks in tasks_by_type.items():
                oldest_age = oldest_by_type[task_type]
                self.stdout.write(f" * {count_style(len(tasks))} {task_type} (oldest={timesince(oldest_age)})")

                if task_type in ("start_flow", "start_flow_batch"):
                    flow_counts = defaultdict(int)
                    for task in tasks:
                        flow_counts[task["task"]["flow_id"]] += 1

                    for flow_id, count in flow_counts.items():
                        flow = Flow.objects.get(id=flow_id)
                        self.stdout.write(f"   - {count_style(count)} {flow.name}")

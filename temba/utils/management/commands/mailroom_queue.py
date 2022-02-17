from django_redis import get_redis_connection

from django.core.management import BaseCommand

from temba.orgs.models import Org
from temba.utils import json


class Command(BaseCommand):
    help = "Dumps contents of mailroom's batch queue"

    def handle(self, *args, **kwargs):
        r = get_redis_connection()

        for org_id, workers in r.zrange("batch:active", 0, -1, withscores=True):
            org = Org.objects.get(id=int(org_id))
            org_queue = f"batch:{org.id}"
            org_task_count = r.zcard(org_queue)

            self.stdout.write(f"{org.name} ({org_task_count} tasks, {int(workers)} workers)")

            for task_str in r.zrange(org_queue, 0, -1):
                task = json.loads(task_str)

                self.stdout.write(f"  {task['type']}")

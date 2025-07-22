from django_valkey import get_valkey_connection

from temba.tests import TembaTest, matchers
from temba.utils import json


class MailroomQueueTest(TembaTest):
    def test_queue_contact_import_batch(self):
        imp = self.create_contact_import("media/test_imports/simple.xlsx")
        imp.start()

        self.assert_org_queued(self.org)
        self.assert_queued_batch_task(
            self.org,
            {
                "type": "import_contact_batch",
                "task": {"contact_import_batch_id": imp.batches.get().id},
                "queued_on": matchers.ISODatetime(),
            },
        )

    def assert_org_queued(self, org):
        r = get_valkey_connection()

        # check we have one org with active tasks
        self.assertEqual(r.zcard("tasks:batch:active"), 1)

        queued_org = json.loads(r.zrange("tasks:batch:active", 0, 1)[0])

        self.assertEqual(queued_org, org.id)

    def assert_queued_batch_task(self, org, expected_task):
        r = get_valkey_connection()

        # check we have one task in the org's queue
        self.assertEqual(r.zcard(f"tasks:batch:{org.id}"), 1)

        # load and check that task
        actual_task = json.loads(r.zrange(f"tasks:batch:{org.id}", 0, 1)[0])

        self.assertEqual(actual_task, expected_task)

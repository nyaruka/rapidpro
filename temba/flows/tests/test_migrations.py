from django.utils import timezone

from temba.flows.models import FlowRun
from temba.tests import MigrationTest
from temba.utils.uuid import uuid4


class FixActivityCountsTest(MigrationTest):
    app = "flows"
    migrate_from = "0407_update_triggers"
    migrate_to = "0408_fix_activity_counts"

    def create_run(self, flow, contact, status, node_uuid):
        return FlowRun.objects.create(
            uuid=uuid4(),
            org=self.org,
            flow=flow,
            contact=contact,
            status=status,
            session_uuid=uuid4(),
            created_on=timezone.now(),
            modified_on=timezone.now(),
            exited_on=timezone.now() if status not in ("A", "W") else None,
            current_node_uuid=node_uuid,
        )

    def setUpBeforeMigration(self, apps):
        contact = self.create_contact("Bob", phone="+1234567890")

        # flow with an actual active run and counts inflated by deleted runs
        self.flow1 = self.create_flow("Test 1")
        self.create_run(self.flow1, contact, FlowRun.STATUS_ACTIVE, "ebb534e1-e2e0-40e9-8652-d195e87d832b")
        self.flow1.counts.create(scope="status:A", count=2)  # from runs deleted whilst active
        self.flow1.counts.create(scope="status:W", count=3)  # from runs deleted whilst waiting
        self.flow1.counts.create(scope="node:4bd7397b-39e4-4c85-9835-7dc408856bf6", count=5)

        # flow with negative drift on a status count
        self.flow2 = self.create_flow("Test 2")
        self.flow2.counts.create(scope="status:W", count=-1)

        # flow with correct counts and an exited status count that shouldn't be touched
        self.flow3 = self.create_flow("Test 3")
        self.create_run(self.flow3, contact, FlowRun.STATUS_WAITING, "bbb71aab-e026-442e-9971-6bc4f48941fb")
        self.create_run(self.flow3, contact, FlowRun.STATUS_COMPLETED, None)
        self.flow3.counts.create(scope="status:C", count=10)  # inflated but not our concern

    def test_migration(self):
        self.assertEqual(
            {
                "status:A": 1,
                "status:W": 0,
                "node:ebb534e1-e2e0-40e9-8652-d195e87d832b": 1,
                "node:4bd7397b-39e4-4c85-9835-7dc408856bf6": 0,
            },
            self.flow1.counts.scope_totals(),
        )
        self.assertEqual({"status:W": 0}, self.flow2.counts.scope_totals())
        self.assertEqual(
            {"status:W": 1, "status:C": 11, "node:bbb71aab-e026-442e-9971-6bc4f48941fb": 1},
            self.flow3.counts.scope_totals(),
        )

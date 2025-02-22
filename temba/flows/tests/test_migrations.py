from uuid import UUID

from django.utils import timezone

from temba.flows.models import FlowRun, FlowSession
from temba.tests import MigrationTest


class BackfillRunSessionUUIDTest(MigrationTest):
    app = "flows"
    migrate_from = "0373_fix_expires_after"
    migrate_to = "0374_backfill_run_session_uuid"

    def setUpBeforeMigration(self, apps):
        flow = self.create_flow("Test 1")
        contact = self.create_contact("Bob", phone="+1234567890")
        session1 = FlowSession.objects.create(
            uuid="8b13db25-83aa-44a4-b84a-ada20cd25f89",
            contact=contact,
            status=FlowSession.STATUS_WAITING,
            output_url="http://sessions.com/123.json",
            created_on=timezone.now(),
        )
        self.session1_run1 = FlowRun.objects.create(
            uuid="bd9e9fd0-6c20-42b4-94ea-c6f129b7fbaf",
            org=self.org,
            session=session1,
            flow=flow,
            contact=contact,
            status="A",
            created_on=timezone.now(),
            modified_on=timezone.now(),
            exited_on=None,
        )
        self.session1_run2 = FlowRun.objects.create(
            uuid="707a7720-5671-49c2-a63c-f0cd2afc06e6",
            org=self.org,
            session=session1,
            flow=flow,
            contact=contact,
            status="W",
            created_on=timezone.now(),
            modified_on=timezone.now(),
            exited_on=None,
        )
        session2 = FlowSession.objects.create(
            uuid="db036eb3-53a5-42ed-ac73-4d3d4badfaaa",
            contact=contact,
            status=FlowSession.STATUS_WAITING,
            output_url="http://sessions.com/123.json",
            created_on=timezone.now(),
        )
        self.session2_run1 = FlowRun.objects.create(
            uuid="f4adc4bb-0a0a-4753-9e0c-47e3a0e86b5a",
            org=self.org,
            session=session2,
            flow=flow,
            contact=contact,
            status="W",
            created_on=timezone.now(),
            modified_on=timezone.now(),
            exited_on=None,
        )
        self.no_session_run = FlowRun.objects.create(
            uuid="c5a6e03a-4d22-4cb7-a2de-130ac1edc7ca",
            org=self.org,
            flow=flow,
            contact=contact,
            status="C",
            created_on=timezone.now(),
            modified_on=timezone.now(),
            exited_on=timezone.now(),
        )

    def test_migration(self):
        self.session1_run1.refresh_from_db()
        self.session1_run2.refresh_from_db()
        self.session2_run1.refresh_from_db()
        self.no_session_run.refresh_from_db()

        self.assertEqual(UUID("8b13db25-83aa-44a4-b84a-ada20cd25f89"), self.session1_run1.session_uuid)
        self.assertEqual(UUID("8b13db25-83aa-44a4-b84a-ada20cd25f89"), self.session1_run2.session_uuid)
        self.assertEqual(UUID("db036eb3-53a5-42ed-ac73-4d3d4badfaaa"), self.session2_run1.session_uuid)
        self.assertIsNone(self.no_session_run.session_uuid)

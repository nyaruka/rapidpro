from datetime import datetime, timezone as tzone

from temba.flows.models import FlowSession
from temba.tests import MigrationTest
from temba.utils.uuid import uuid7


class BackfillSessionContactUUIDTest(MigrationTest):
    app = "flows"
    migrate_from = "0391_flowsession_current_flow_uuid"
    migrate_to = "0392_backfill_session_flow_uuid"

    def setUpBeforeMigration(self, apps):
        contact = self.create_contact("Ann")
        self.flow1 = self.create_flow("Flow 1")
        self.flow2 = self.create_flow("Flow 2")

        self.session1 = FlowSession.objects.create(
            uuid=uuid7(),
            contact=contact,
            output_url="http://sessions.com/123.json",
            status=FlowSession.STATUS_WAITING,
            current_flow=self.flow1,
            ended_on=datetime(2025, 1, 15, 0, 0, 0, 0, tzone.utc),
        )
        self.session2 = FlowSession.objects.create(
            uuid=uuid7(),
            contact=contact,
            output_url="http://sessions.com/234.json",
            status=FlowSession.STATUS_WAITING,
            current_flow=self.flow2,
            ended_on=datetime(2025, 1, 15, 0, 0, 0, 0, tzone.utc),
        )
        self.session3 = FlowSession.objects.create(
            uuid=uuid7(),
            contact=contact,
            output_url="http://sessions.com/345.json",
            status=FlowSession.STATUS_COMPLETED,
            current_flow=None,  # will be ignored
            ended_on=datetime(2025, 1, 15, 0, 0, 0, 0, tzone.utc),
        )

    def test_migration(self):
        self.session1.refresh_from_db()
        self.session2.refresh_from_db()
        self.session3.refresh_from_db()

        self.assertEqual(self.flow1.uuid, str(self.session1.current_flow_uuid))
        self.assertEqual(self.flow2.uuid, str(self.session2.current_flow_uuid))
        self.assertIsNone(self.session3.current_flow_uuid)

from datetime import datetime, timezone as tzone

from temba.flows.models import FlowSession
from temba.tests import MigrationTest
from temba.utils.uuid import uuid7


class BackfillSessionContactUUIDTest(MigrationTest):
    app = "flows"
    migrate_from = "0389_flowsession_contact_uuid_alter_flowsession_call_and_more"
    migrate_to = "0390_backfill_session_contact_uuid"

    def setUpBeforeMigration(self, apps):
        self.contact1 = self.create_contact("Ann")
        self.contact2 = self.create_contact("Bob")

        self.session1 = FlowSession.objects.create(
            uuid=uuid7(),
            contact=self.contact1,
            output_url="http://sessions.com/123.json",
            status=FlowSession.STATUS_WAITING,
            ended_on=datetime(2025, 1, 15, 0, 0, 0, 0, tzone.utc),
        )
        self.session2 = FlowSession.objects.create(
            uuid=uuid7(),
            contact=self.contact2,
            output_url="http://sessions.com/234.json",
            status=FlowSession.STATUS_WAITING,
            ended_on=datetime(2025, 1, 15, 0, 0, 0, 0, tzone.utc),
        )
        self.session3 = FlowSession.objects.create(
            uuid=uuid7(),
            contact=self.contact2,
            output_url="http://sessions.com/345.json",
            status=FlowSession.STATUS_COMPLETED,  # will be ignored
            ended_on=datetime(2025, 1, 15, 0, 0, 0, 0, tzone.utc),
        )

    def test_migration(self):
        self.session1.refresh_from_db()
        self.session2.refresh_from_db()
        self.session3.refresh_from_db()

        self.assertEqual(self.contact1.uuid, str(self.session1.contact_uuid))
        self.assertEqual(self.contact2.uuid, str(self.session2.contact_uuid))
        self.assertIsNone(self.session3.contact_uuid)

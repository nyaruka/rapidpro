from datetime import datetime, timezone as tzone

from temba.ivr.models import Call
from temba.tests import MigrationTest


class BackfillCallUUIDsTest(MigrationTest):
    app = "ivr"
    migrate_from = "0036_squashed"
    migrate_to = "0037_backfill_call_uuid"

    def setUpBeforeMigration(self, apps):
        contact = self.create_contact("Ann", phone="+123456789")

        self.call1 = Call.objects.create(
            org=self.org,
            channel=self.channel,
            direction=Call.DIRECTION_IN,
            contact=contact,
            contact_urn=contact.get_urn(),
            status=Call.STATUS_IN_PROGRESS,
            created_on=datetime(2025, 8, 11, 20, 36, 41, 114764, tzinfo=tzone.utc),
        )
        self.call2 = Call.objects.create(
            uuid="01989ad9-7c1a-7b8d-a59e-141c265730dc",
            org=self.org,
            channel=self.channel,
            direction=Call.DIRECTION_IN,
            contact=contact,
            contact_urn=contact.get_urn(),
            status=Call.STATUS_IN_PROGRESS,
            created_on=datetime(2025, 8, 11, 20, 36, 41, 116000, tzinfo=tzone.utc),
        )

    def test_migration(self):
        self.call1.refresh_from_db()
        self.call2.refresh_from_db()

        self.assertTrue(str(self.call1.uuid).startswith("01989ad9-7c1a-7"))
        self.assertEqual("01989ad9-7c1a-7b8d-a59e-141c265730dc", str(self.call2.uuid))  # unchanged

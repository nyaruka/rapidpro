from datetime import datetime, timezone as tzone
from decimal import Decimal

from temba.ivr.models import Call
from temba.tests import MigrationTest, cleanup, matchers
from temba.tests.dynamo import dynamo_scan_all
from temba.utils import dynamo


class BackfillCallEventsTest(MigrationTest):
    app = "ivr"
    migrate_from = "0038_alter_call_uuid"
    migrate_to = "0039_backfill_call_events"

    def setUpBeforeMigration(self, apps):
        contact = self.create_contact("Ann", phone="+1234567890", uuid="40248365-230d-4a29-8dbc-c89e43dd3adf")
        deleted_contact = self.create_contact("Deleted", uuid="1d48402f-df4c-44d8-b648-e0180f6a0dd2", is_active=False)

        Call.objects.create(
            uuid="0198e29d-a536-7cf4-b78b-a33eebe0ce58",
            org=self.org,
            channel=self.channel,
            direction=Call.DIRECTION_IN,
            contact=contact,
            contact_urn=contact.get_urn(),
            status=Call.STATUS_IN_PROGRESS,
            created_on=datetime(2025, 8, 11, 20, 36, 0, 0, tzinfo=tzone.utc),
        )
        Call.objects.create(
            uuid="0198e29d-c924-7047-ba48-e980b817c7ca",
            org=self.org,
            channel=self.channel,
            direction=Call.DIRECTION_OUT,
            contact=contact,
            contact_urn=contact.get_urn(),
            status=Call.STATUS_IN_PROGRESS,
            created_on=datetime(2025, 8, 11, 20, 38, 0, 0, tzinfo=tzone.utc),
        )
        Call.objects.create(  # for a deleted contact
            uuid="0198e29e-49b1-7475-860f-b2d39e6c2831",
            org=self.org,
            channel=self.channel,
            direction=Call.DIRECTION_IN,
            contact=deleted_contact,
            contact_urn=contact.get_urn(),
            status=Call.STATUS_IN_PROGRESS,
            created_on=datetime(2025, 8, 11, 20, 36, 0, 0, tzinfo=tzone.utc),
        )

    @cleanup(dynamodb=True)
    def test_migration(self):
        items = dynamo_scan_all(dynamo.HISTORY)
        self.assertEqual(
            [
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": matchers.String(pattern=r"evt#[a-z0-9\-]{36}"),
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "call_received",
                        "created_on": "2025-08-11T20:36:00+00:00",
                        "call": {
                            "uuid": "0198e29d-a536-7cf4-b78b-a33eebe0ce58",
                            "urn": "tel:1234567890",
                            "channel": {"uuid": str(self.channel.uuid), "name": self.channel.name},
                        },
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": matchers.String(pattern=r"evt#[a-z0-9\-]{36}"),
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "call_created",
                        "created_on": "2025-08-11T20:38:00+00:00",
                        "call": {
                            "uuid": "0198e29d-c924-7047-ba48-e980b817c7ca",
                            "urn": "tel:1234567890",
                            "channel": {"uuid": str(self.channel.uuid), "name": self.channel.name},
                        },
                    },
                },
            ],
            items,
        )

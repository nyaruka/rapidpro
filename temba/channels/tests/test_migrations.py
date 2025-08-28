from datetime import datetime, timezone as tzone
from decimal import Decimal

from temba.channels.models import ChannelEvent
from temba.tests import MigrationTest, cleanup
from temba.tests.dynamo import dynamo_scan_all
from temba.utils import dynamo


class TestBackfillChannelEvents(MigrationTest):
    app = "channels"
    migrate_from = "0207_squashed"
    migrate_to = "0208_backfill_channel_events"

    def setUpBeforeMigration(self, apps):
        contact = self.create_contact("Ann", uuid="40248365-230d-4a29-8dbc-c89e43dd3adf")
        deleted_contact = self.create_contact("Deleted", uuid="1d48402f-df4c-44d8-b648-e0180f6a0dd2", is_active=False)
        self.optin = self.create_optin("Jokes")

        ChannelEvent.objects.create(  # should become chat_started without params
            uuid="0198ebde-a7f0-7079-b470-3bc9c1a4cf77",
            org=self.org,
            channel=self.channel,
            event_type=ChannelEvent.TYPE_NEW_CONVERSATION,
            contact=contact,
            created_on=datetime(2025, 8, 11, 20, 36, 0, 0, tzinfo=tzone.utc),
            occurred_on=datetime(2025, 8, 11, 20, 36, 0, 0, tzinfo=tzone.utc),
        )
        ChannelEvent.objects.create(  # should become chat_started with params
            uuid="0198ebde-a7f0-7401-b13f-19dc935070c3",
            org=self.org,
            channel=self.channel,
            event_type=ChannelEvent.TYPE_REFERRAL,
            extra={"source": "facebook", "referrer_id": "acme"},
            contact=contact,
            created_on=datetime(2025, 8, 11, 20, 37, 0, 0, tzinfo=tzone.utc),
            occurred_on=datetime(2025, 8, 11, 20, 37, 0, 0, tzinfo=tzone.utc),
        )
        ChannelEvent.objects.create(  # should become call_missed
            uuid="0198ebde-a7f0-746b-a5c9-aa0833bfe713",
            org=self.org,
            channel=self.channel,
            event_type=ChannelEvent.TYPE_CALL_IN_MISSED,
            extra={"duration": 0},
            contact=contact,
            created_on=datetime(2025, 8, 11, 20, 38, 0, 0, tzinfo=tzone.utc),
            occurred_on=datetime(2025, 8, 11, 20, 38, 0, 0, tzinfo=tzone.utc),
        )
        ChannelEvent.objects.create(  # should become optin_started
            uuid="0198ebde-a7f0-7667-bb8f-41cd7d36877b",
            org=self.org,
            channel=self.channel,
            event_type=ChannelEvent.TYPE_OPTIN,
            contact=contact,
            optin=self.optin,
            created_on=datetime(2025, 8, 11, 20, 39, 0, 0, tzinfo=tzone.utc),
            occurred_on=datetime(2025, 8, 11, 20, 39, 0, 0, tzinfo=tzone.utc),
        )
        ChannelEvent.objects.create(  # should become optin_stopped
            uuid="0198ebde-a7f0-7685-8bed-fce708c026bf",
            org=self.org,
            channel=self.channel,
            event_type=ChannelEvent.TYPE_OPTOUT,
            contact=contact,
            optin=self.optin,
            created_on=datetime(2025, 8, 11, 20, 40, 0, 0, tzinfo=tzone.utc),
            occurred_on=datetime(2025, 8, 11, 20, 40, 0, 0, tzinfo=tzone.utc),
        )
        ChannelEvent.objects.create(  # for a deleted contact
            uuid="0198c7db-4291-744b-be58-45081577ab41",
            org=self.org,
            channel=self.channel,
            event_type=ChannelEvent.TYPE_NEW_CONVERSATION,
            contact=deleted_contact,
            created_on=datetime(2025, 8, 11, 20, 50, 0, 0, tzinfo=tzone.utc),
            occurred_on=datetime(2025, 8, 11, 20, 50, 0, 0, tzinfo=tzone.utc),
        )
        ChannelEvent.objects.create(  # for an unmigrated event type
            uuid="0198cd93-4966-7af6-85c7-696c560be023",
            org=self.org,
            channel=self.channel,
            event_type=ChannelEvent.TYPE_WELCOME_MESSAGE,
            contact=contact,
            created_on=datetime(2025, 8, 11, 20, 51, 0, 0, tzinfo=tzone.utc),
            occurred_on=datetime(2025, 8, 11, 20, 51, 0, 0, tzinfo=tzone.utc),
        )

    @cleanup(dynamodb=True)
    def test_migration(self):
        items = dynamo_scan_all(dynamo.HISTORY)
        self.assertEqual(
            [
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": "evt#0198ebde-a7f0-7079-b470-3bc9c1a4cf77",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "chat_started",
                        "created_on": "2025-08-11T20:36:00+00:00",
                        "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": "evt#0198ebde-a7f0-7401-b13f-19dc935070c3",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "chat_started",
                        "created_on": "2025-08-11T20:37:00+00:00",
                        "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                        "params": {"source": "facebook", "referrer_id": "acme"},
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": "evt#0198ebde-a7f0-746b-a5c9-aa0833bfe713",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "call_missed",
                        "created_on": "2025-08-11T20:38:00+00:00",
                        "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": "evt#0198ebde-a7f0-7667-bb8f-41cd7d36877b",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "optin_started",
                        "created_on": "2025-08-11T20:39:00+00:00",
                        "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                        "optin": {"uuid": str(self.optin.uuid), "name": "Jokes"},
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": "evt#0198ebde-a7f0-7685-8bed-fce708c026bf",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "optin_stopped",
                        "created_on": "2025-08-11T20:40:00+00:00",
                        "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                        "optin": {"uuid": str(self.optin.uuid), "name": "Jokes"},
                    },
                },
            ],
            items,
        )

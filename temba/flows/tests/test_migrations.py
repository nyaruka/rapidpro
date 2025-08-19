from datetime import datetime, timezone as tzone
from decimal import Decimal

from temba.flows.models import FlowRun
from temba.tests import MigrationTest, matchers
from temba.utils import dynamo
from temba.utils.dynamo import testing as dytest


class BackfillRunStartedEndedEventsTest(MigrationTest):
    app = "flows"
    migrate_from = "0394_remove_flowsession_call_remove_flowsession_contact_and_more"
    migrate_to = "0395_backfill_run_started_ended_events"

    def setUpBeforeMigration(self, apps):
        self.flow = self.create_flow("Test Flow")
        contact = self.create_contact("Ann", uuid="40248365-230d-4a29-8dbc-c89e43dd3adf")
        deleted_contact = self.create_contact("Deleted", uuid="1d48402f-df4c-44d8-b648-e0180f6a0dd2", is_active=False)

        self.run1 = FlowRun.objects.create(  # completed
            uuid="0198c7da-d9fb-7844-a353-a1676d9e39c0",
            org=self.org,
            flow=self.flow,
            contact=contact,
            status=FlowRun.STATUS_COMPLETED,
            created_on=datetime(2025, 8, 11, 20, 36, 0, 0, tzinfo=tzone.utc),
            exited_on=datetime(2025, 8, 11, 20, 37, 0, 0, tzinfo=tzone.utc),
        )
        self.run2 = FlowRun.objects.create(  # active
            uuid="0198c7db-2086-7402-b5ca-8da67f2e3a8c",
            org=self.org,
            flow=self.flow,
            contact=contact,
            status=FlowRun.STATUS_ACTIVE,
            created_on=datetime(2025, 8, 11, 20, 38, 0, 0, tzinfo=tzone.utc),
        )
        self.run3 = FlowRun.objects.create(  # for a deleted contact
            uuid="0198c7db-4291-744b-be58-45081577ab41",
            org=self.org,
            flow=self.flow,
            contact=deleted_contact,
            status=FlowRun.STATUS_COMPLETED,
            created_on=datetime(2025, 8, 11, 20, 36, 0, 0, tzinfo=tzone.utc),
            exited_on=datetime(2025, 8, 11, 20, 37, 0, 0, tzinfo=tzone.utc),
        )

    def tearDown(self):
        dytest.truncate(dynamo.HISTORY)

        return super().tearDown()

    def test_migration(self):
        items = dytest.scan_all(dynamo.HISTORY)
        self.assertEqual(
            [
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": matchers.String(pattern=r"evt#[a-z0-9\-]{36}"),
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "run_started",
                        "created_on": "2025-08-11T20:36:00+00:00",
                        "run_uuid": "0198c7da-d9fb-7844-a353-a1676d9e39c0",
                        "flow": {"uuid": str(self.flow.uuid), "name": "Test Flow"},
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": matchers.String(pattern=r"evt#[a-z0-9\-]{36}"),
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "run_ended",
                        "created_on": "2025-08-11T20:37:00+00:00",
                        "run_uuid": "0198c7da-d9fb-7844-a353-a1676d9e39c0",
                        "flow": {"uuid": str(self.flow.uuid), "name": "Test Flow"},
                        "status": "completed",
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": matchers.String(pattern=r"evt#[a-z0-9\-]{36}"),
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "run_started",
                        "created_on": "2025-08-11T20:38:00+00:00",
                        "run_uuid": "0198c7db-2086-7402-b5ca-8da67f2e3a8c",
                        "flow": {"uuid": str(self.flow.uuid), "name": "Test Flow"},
                    },
                },
            ],
            items,
        )

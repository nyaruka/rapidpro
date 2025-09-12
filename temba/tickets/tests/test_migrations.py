from datetime import datetime, timezone as tzone
from decimal import Decimal

from temba.tests import MigrationTest, cleanup
from temba.tests.dynamo import dynamo_scan_all
from temba.tickets.models import Ticket, TicketEvent, Topic
from temba.utils import dynamo


class UpdateTicketUUIDsTest(MigrationTest):
    app = "tickets"
    migrate_from = "0082_alter_ticketevent_uuid"
    migrate_to = "0083_update_ticket_uuids"

    def setUpBeforeMigration(self, apps):
        contact = self.create_contact("Ann")

        self.ticket1 = Ticket.objects.create(
            uuid="c7371b3b-5b35-4a03-aaf9-632335fb7e77",
            org=contact.org,
            contact=contact,
            topic=contact.org.default_ticket_topic,
            status=Ticket.STATUS_OPEN,
            opened_on=datetime(2025, 8, 11, 20, 36, 41, 114764, tzinfo=tzone.utc),
        )
        self.ticket2 = Ticket.objects.create(
            uuid="01989ad9-7c1a-7b8d-a59e-141c265730dc",
            org=contact.org,
            contact=contact,
            topic=contact.org.default_ticket_topic,
            status=Ticket.STATUS_OPEN,
            opened_on=datetime(2025, 8, 11, 20, 36, 41, 116000, tzinfo=tzone.utc),
        )

    def test_migration(self):
        self.ticket1.refresh_from_db()
        self.ticket2.refresh_from_db()

        self.assertTrue(str(self.ticket1.uuid).startswith("01989ad9-7c1a-7"))
        self.assertEqual("01989ad9-7c1a-7b8d-a59e-141c265730dc", str(self.ticket2.uuid))  # unchanged


class BackfilTicketEventsTest(MigrationTest):
    app = "tickets"
    migrate_from = "0085_remove_ticket_tickets_contact_open_and_more"
    migrate_to = "0086_backfill_ticket_events"

    def setUpBeforeMigration(self, apps):
        self.sales = Topic.create(self.org, self.admin, "Sales")
        contact = self.create_contact("Ann", uuid="40248365-230d-4a29-8dbc-c89e43dd3adf")
        deleted_contact = self.create_contact("Deleted", uuid="1d48402f-df4c-44d8-b648-e0180f6a0dd2", is_active=False)

        ticket1 = Ticket.objects.create(
            uuid="01992f54-5ab6-717a-a39e-e8ca91fb7262",
            org=contact.org,
            contact=contact,
            topic=contact.org.default_ticket_topic,
            status=Ticket.STATUS_OPEN,
            opened_on=datetime(2025, 8, 11, 20, 36, 41, 114764, tzinfo=tzone.utc),
        )
        deleted_contact_ticket = Ticket.objects.create(
            uuid="01992f54-5ab6-725e-be9c-0c6407efd755",
            org=deleted_contact.org,
            contact=deleted_contact,
            topic=deleted_contact.org.default_ticket_topic,
            status=Ticket.STATUS_OPEN,
            opened_on=datetime(2025, 8, 11, 20, 36, 41, 116000, tzinfo=tzone.utc),
        )

        TicketEvent.objects.create(
            uuid="01992f54-5ab6-7498-a7f2-6aa246e45cfe",
            org=self.org,
            ticket=ticket1,
            contact=contact,
            event_type=TicketEvent.TYPE_OPENED,
            note="Interesting",
            topic=None,
            assignee=None,
            created_by=None,
            created_on=datetime(2025, 8, 11, 20, 36, 0, 0, tzinfo=tzone.utc),
        )

        TicketEvent.objects.create(  # assignee changed to agent by admin
            uuid="01992f54-5ab6-7658-a5d4-bdb05863ec56",
            org=self.org,
            ticket=ticket1,
            contact=contact,
            event_type=TicketEvent.TYPE_ASSIGNED,
            assignee=self.agent,
            created_by=self.admin,
            created_on=datetime(2025, 8, 11, 20, 36, 0, 0, tzinfo=tzone.utc),
        )

        TicketEvent.objects.create(  # assignee changed to nobody
            uuid="01992f54-5ab6-768d-a7a5-caa2b5907a64",
            org=self.org,
            ticket=ticket1,
            contact=contact,
            event_type=TicketEvent.TYPE_ASSIGNED,
            assignee=None,
            created_on=datetime(2025, 8, 11, 20, 36, 0, 0, tzinfo=tzone.utc),
        )

        TicketEvent.objects.create(  # topic changed to sales
            uuid="01992f54-5ab6-783e-994d-8aa1e66492ca",
            org=self.org,
            ticket=ticket1,
            contact=contact,
            event_type=TicketEvent.TYPE_TOPIC_CHANGED,
            topic=self.sales,
            created_on=datetime(2025, 8, 11, 20, 36, 0, 0, tzinfo=tzone.utc),
        )

        TicketEvent.objects.create(  # closed
            uuid="01992f54-5ab6-7887-95bc-d1869aa61936",
            org=self.org,
            ticket=ticket1,
            contact=contact,
            event_type=TicketEvent.TYPE_CLOSED,
            created_on=datetime(2025, 8, 11, 20, 36, 0, 0, tzinfo=tzone.utc),
        )

        TicketEvent.objects.create(  # reopened by admin
            uuid="01992f54-5ab6-7979-95db-6398d3fce898",
            org=self.org,
            ticket=ticket1,
            contact=contact,
            event_type=TicketEvent.TYPE_REOPENED,
            created_by=self.admin,
            created_on=datetime(2025, 8, 11, 20, 36, 0, 0, tzinfo=tzone.utc),
        )

        TicketEvent.objects.create(  # note added by editor
            uuid="01992f54-5ab6-7ac5-96d7-94cf6edc5f2b",
            org=self.org,
            ticket=ticket1,
            contact=contact,
            event_type=TicketEvent.TYPE_NOTE_ADDED,
            note="We need to follow up",
            created_by=self.editor,
            created_on=datetime(2025, 8, 11, 20, 36, 0, 0, tzinfo=tzone.utc),
        )

        TicketEvent.objects.create(  # for a deleted contact
            uuid="01992f54-5ab6-7d45-aa0c-f95cfd7c9bc2",
            org=self.org,
            ticket=deleted_contact_ticket,
            contact=deleted_contact,
            event_type=TicketEvent.TYPE_OPENED,
            created_on=datetime(2025, 8, 11, 20, 36, 0, 0, tzinfo=tzone.utc),
        )

    @cleanup(dynamodb=True)
    def test_migration(self):
        items = dynamo_scan_all(dynamo.HISTORY)
        self.assertEqual(
            [
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": "evt#01992f54-5ab6-7498-a7f2-6aa246e45cfe",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "ticket_opened",
                        "created_on": "2025-08-11T20:36:00+00:00",
                        "ticket": {
                            "uuid": "01992f54-5ab6-717a-a39e-e8ca91fb7262",
                            "status": "open",
                            "assignee": None,
                            "topic": {"uuid": str(self.org.default_ticket_topic.uuid), "name": "General"},
                        },
                        "note": "Interesting",
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": "evt#01992f54-5ab6-7658-a5d4-bdb05863ec56",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "ticket_assignee_changed",
                        "created_on": "2025-08-11T20:36:00+00:00",
                        "ticket_uuid": "01992f54-5ab6-717a-a39e-e8ca91fb7262",
                        "assignee": {"uuid": str(self.agent.uuid), "name": "Agnes"},
                        "_user_id": Decimal(self.admin.id),
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": "evt#01992f54-5ab6-768d-a7a5-caa2b5907a64",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "ticket_assignee_changed",
                        "created_on": "2025-08-11T20:36:00+00:00",
                        "ticket_uuid": "01992f54-5ab6-717a-a39e-e8ca91fb7262",
                        "assignee": None,
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": "evt#01992f54-5ab6-783e-994d-8aa1e66492ca",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "ticket_topic_changed",
                        "created_on": "2025-08-11T20:36:00+00:00",
                        "ticket_uuid": "01992f54-5ab6-717a-a39e-e8ca91fb7262",
                        "topic": {"uuid": str(self.sales.uuid), "name": "Sales"},
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": "evt#01992f54-5ab6-7887-95bc-d1869aa61936",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "ticket_closed",
                        "created_on": "2025-08-11T20:36:00+00:00",
                        "ticket_uuid": "01992f54-5ab6-717a-a39e-e8ca91fb7262",
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": "evt#01992f54-5ab6-7979-95db-6398d3fce898",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "ticket_reopened",
                        "created_on": "2025-08-11T20:36:00+00:00",
                        "ticket_uuid": "01992f54-5ab6-717a-a39e-e8ca91fb7262",
                        "_user_id": Decimal(self.admin.id),
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": "evt#01992f54-5ab6-7ac5-96d7-94cf6edc5f2b",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "ticket_note_added",
                        "created_on": "2025-08-11T20:36:00+00:00",
                        "ticket_uuid": "01992f54-5ab6-717a-a39e-e8ca91fb7262",
                        "note": "We need to follow up",
                        "_user_id": Decimal(self.editor.id),
                    },
                },
            ],
            items,
        )

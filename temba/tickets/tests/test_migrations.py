from datetime import datetime, timezone as tzone

from temba.tests import MigrationTest
from temba.tickets.models import Ticket


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
            topic=contact.org.default_topic,
            status=Ticket.STATUS_OPEN,
            opened_on=datetime(2025, 8, 11, 20, 36, 41, 114764, tzinfo=tzone.utc),
        )
        self.ticket2 = Ticket.objects.create(
            uuid="01989ad9-7c1a-7b8d-a59e-141c265730dc",
            org=contact.org,
            contact=contact,
            topic=contact.org.default_topic,
            status=Ticket.STATUS_OPEN,
            opened_on=datetime(2025, 8, 11, 20, 36, 41, 116000, tzinfo=tzone.utc),
        )

    def test_migration(self):
        self.ticket1.refresh_from_db()
        self.ticket2.refresh_from_db()

        self.assertTrue(str(self.ticket1.uuid).startswith("01989ad9-7c1a-7"))
        self.assertEqual("01989ad9-7c1a-7b8d-a59e-141c265730dc", str(self.ticket2.uuid))  # unchanged

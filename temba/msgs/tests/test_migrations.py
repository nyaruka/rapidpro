from temba.msgs.models import MsgFolder
from temba.tests import MigrationTest


class FixFolderCountsTest(MigrationTest):
    app = "msgs"
    migrate_from = "0291_update_triggers"
    migrate_to = "0292_fix_folder_counts"

    def setUpBeforeMigration(self, apps):
        contact1 = self.create_contact("Ann", phone="+1234567890", org=self.org)
        flow1 = self.create_flow("Flow1", org=self.org)

        contact2 = self.create_contact("Bob", phone="+1234567890", org=self.org2)
        channel2 = self.create_channel("A", "Android", "1234", org=self.org2)

        self.create_incoming_msg(contact1, "M", status="H", visibility="V", flow=None)
        self.create_incoming_msg(contact1, "M", status="H", visibility="V", flow=None)
        self.create_incoming_msg(contact1, "M", status="H", visibility="V", flow=None)
        self.create_incoming_msg(contact1, "M", status="H", visibility="V", flow=None)
        self.create_incoming_msg(contact1, "M", status="H", visibility="V", flow=None, voice=True)
        self.create_incoming_msg(contact1, "M", status="H", visibility="V", flow=None, voice=True)
        self.create_incoming_msg(contact1, "M", status="H", visibility="V", flow=flow1)
        self.create_incoming_msg(contact1, "M", status="H", visibility="V", flow=flow1)
        self.create_incoming_msg(contact1, "M", status="H", visibility="V", flow=flow1, voice=True)
        self.create_incoming_msg(contact1, "M", status="H", visibility="A", flow=None)
        self.create_incoming_msg(contact1, "M", status="H", visibility="A", flow=flow1)
        self.create_incoming_msg(contact1, "M", status="H", visibility="A", flow=flow1, voice=True)
        self.create_incoming_msg(contact1, "M", status="H", visibility="A", flow=None)
        self.create_incoming_msg(contact1, "M", status="P", visibility="D", flow=None)
        self.create_incoming_msg(contact1, "M", status="H", visibility="D", flow=None)
        self.create_outgoing_msg(contact1, "M", status="S", flow=None)
        self.create_outgoing_msg(contact1, "M", status="S", flow=None, voice=True)

        # we've fixed the db triggers in the previous migration to include IVR messages but we need to pretend these
        # messages were added prior to that and so aren't included in the counts
        self.org.counts.create(scope="msgs:folder:I", is_squashed=False, count=-2)
        self.org.counts.create(scope="msgs:folder:W", is_squashed=False, count=-1)
        self.org.counts.create(scope="msgs:folder:A", is_squashed=False, count=-1)

        # org #2 will be skipped because it doesn't have any IVR messages
        self.create_incoming_msg(contact2, "M", status="H", visibility="V", channel=channel2)
        self.create_incoming_msg(contact2, "M", status="H", visibility="A", channel=channel2)

    def test_migration(self):
        self.assertEqual(
            MsgFolder.get_counts(self.org),
            {
                MsgFolder.INBOX: 6,
                MsgFolder.HANDLED: 3,
                MsgFolder.ARCHIVED: 4,
                MsgFolder.OUTBOX: 0,
                MsgFolder.SENT: 2,
                MsgFolder.FAILED: 0,
                "scheduled": 0,
                "calls": 0,
            },
        )
        self.assertEqual(
            MsgFolder.get_counts(self.org2),
            {
                MsgFolder.INBOX: 1,
                MsgFolder.HANDLED: 0,
                MsgFolder.ARCHIVED: 1,
                MsgFolder.OUTBOX: 0,
                MsgFolder.SENT: 0,
                MsgFolder.FAILED: 0,
                "scheduled": 0,
                "calls": 0,
            },
        )

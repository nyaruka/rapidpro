from importlib import import_module
from unittest.mock import patch

from temba.msgs.models import Msg
from temba.tests import MigrationTest


class BackfillBroadcastUUIDsTest(MigrationTest):
    app = "msgs"
    migrate_from = "0293_broadcast_uuid"
    migrate_to = "0294_backfill_bcast_uuid"

    def setUpBeforeMigration(self, apps):
        self.bcast1 = self.create_broadcast(self.admin, {"eng": {"text": "Hello"}})
        self.bcast1.uuid = None
        self.bcast1.save(update_fields=["uuid"])

        self.bcast2 = self.create_broadcast(self.admin, {"eng": {"text": "Hello"}})
        self.bcast2.uuid = "01997d23-81ec-73c2-a3da-4d8d69025931"
        self.bcast2.save(update_fields=["uuid"])

    def test_migration(self):
        self.bcast1.refresh_from_db()
        self.assertIsNotNone(self.bcast1.uuid)
        self.bcast2.refresh_from_db()
        self.assertEqual("01997d23-81ec-73c2-a3da-4d8d69025931", str(self.bcast2.uuid))  # unchanged


class BackfillMsgFolderTest(MigrationTest):
    app = "msgs"
    migrate_from = "0309_msg_folder"
    migrate_to = "0310_backfill_msg_folder"

    def setUpBeforeMigration(self, apps):
        contact = self.create_contact("Bob", phone="+1234567890")
        flow = self.create_flow("Test")

        self.inbox = self.create_incoming_msg(contact, "Hi")
        self.handled = self.create_incoming_msg(contact, "Hi", flow=flow)
        self.archived = self.create_incoming_msg(contact, "Hi", visibility=Msg.VISIBILITY_ARCHIVED)
        self.outbox = self.create_outgoing_msg(contact, "Hi", status=Msg.STATUS_QUEUED)
        self.sent = self.create_outgoing_msg(contact, "Hi", status=Msg.STATUS_SENT)
        self.failed = self.create_outgoing_msg(contact, "Hi", status=Msg.STATUS_FAILED)
        self.pending = self.create_incoming_msg(contact, "Hi", status=Msg.STATUS_PENDING)

        # deleted and unhandled take precedence over the user facing folders
        self.deleted = self.create_incoming_msg(contact, "Hi", visibility=Msg.VISIBILITY_DELETED_BY_USER)
        self.deleted_by_sender = self.create_incoming_msg(
            contact, "Hi", status=Msg.STATUS_PENDING, visibility=Msg.VISIBILITY_DELETED_BY_SENDER
        )
        self.pending_archived = self.create_incoming_msg(
            contact, "Hi", status=Msg.STATUS_PENDING, visibility=Msg.VISIBILITY_ARCHIVED
        )

        # a message that already has a folder shouldn't be recalculated
        self.already_set = self.create_incoming_msg(contact, "Hi")
        Msg.objects.filter(id=self.already_set.id).update(folder=Msg.FOLDER_ARCHIVED)

    def test_migration(self):
        def assert_folder(msg, expected):
            msg.refresh_from_db()
            self.assertEqual(expected, msg.folder, f"folder mismatch for msg #{msg.id}")

        assert_folder(self.inbox, Msg.FOLDER_INBOX)
        assert_folder(self.handled, Msg.FOLDER_HANDLED)
        assert_folder(self.archived, Msg.FOLDER_ARCHIVED)
        assert_folder(self.outbox, Msg.FOLDER_OUTBOX)
        assert_folder(self.sent, Msg.FOLDER_SENT)
        assert_folder(self.failed, Msg.FOLDER_FAILED)
        assert_folder(self.pending, Msg.FOLDER_PENDING)
        assert_folder(self.deleted, Msg.FOLDER_DELETED)
        assert_folder(self.deleted_by_sender, Msg.FOLDER_DELETED)
        assert_folder(self.pending_archived, Msg.FOLDER_PENDING)

        assert_folder(self.already_set, Msg.FOLDER_ARCHIVED)  # not recalculated


class BackfillMsgFolderPagingTest(MigrationTest):
    """
    The backfill walks the id range in batches of BATCH_SIZE ids, so with a realistic batch size a test fixture never
    runs the loop more than once. Shrink it so that advancing between batches is actually exercised.
    """

    app = "msgs"
    migrate_from = "0309_msg_folder"
    migrate_to = "0310_backfill_msg_folder"

    def setUp(self):
        # has to be patched before super() runs the migration
        migration = import_module("temba.msgs.migrations.0310_backfill_msg_folder")
        patcher = patch.object(migration, "BATCH_SIZE", 1)
        patcher.start()
        self.addCleanup(patcher.stop)

        super().setUp()

    def setUpBeforeMigration(self, apps):
        contact = self.create_contact("Bob", phone="+1234567890")

        # enough messages to span several batches
        self.msgs = [self.create_incoming_msg(contact, f"Hi {m}") for m in range(5)]

    def test_migration(self):
        # every message filled in, so no batch was skipped
        for msg in self.msgs:
            msg.refresh_from_db()
            self.assertEqual(Msg.FOLDER_INBOX, msg.folder, f"folder mismatch for msg #{msg.id}")


class BackfillMsgFolderNoMessagesTest(MigrationTest):
    app = "msgs"
    migrate_from = "0309_msg_folder"
    migrate_to = "0310_backfill_msg_folder"

    def test_migration(self):
        # a workspace with no messages at all has no id range to walk
        self.assertEqual(0, Msg.objects.count())

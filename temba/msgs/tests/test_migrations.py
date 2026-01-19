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


class BackfillExternalIdentifierTest(MigrationTest):
    app = "msgs"
    migrate_from = "0300_msg_external_identifier_and_more"
    migrate_to = "0301_backfill_external_identifier"

    def setUpBeforeMigration(self, apps):
        contact = self.create_contact("Bob", phone="+1234567890")

        # msg with external_id but no external_identifier - should be backfilled
        self.msg1 = self.create_incoming_msg(contact, "Hello", external_id="ext-123")
        self.msg1.external_identifier = None
        self.msg1.save(update_fields=["external_identifier"])

        # msg with both external_id and external_identifier - should be unchanged
        self.msg2 = self.create_incoming_msg(contact, "World", external_id="ext-456")
        self.msg2.external_identifier = "already-set"
        self.msg2.save(update_fields=["external_identifier"])

        # msg with no external_id - should be unchanged
        self.msg3 = self.create_incoming_msg(contact, "Test")

    def test_migration(self):
        self.msg1.refresh_from_db()
        self.assertEqual("ext-123", self.msg1.external_identifier)  # backfilled from external_id

        self.msg2.refresh_from_db()
        self.assertEqual("already-set", self.msg2.external_identifier)  # unchanged

        self.msg3.refresh_from_db()
        self.assertIsNone(self.msg3.external_identifier)  # still null

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


class BackfillMsgQuickRepliesTest(MigrationTest):
    app = "msgs"
    migrate_from = "0304_msg_quickreplies"
    migrate_to = "0305_backfill_msg_quickreplies"

    def setUpBeforeMigration(self, apps):
        joe = self.create_contact("Joe Blow", phone="+250788123123")

        # msg with text quick replies including one with extra
        self.msg1 = self.create_outgoing_msg(joe, "Pick one", quick_replies=["Yes", "No<extra>Let's go!"])

        # msg with a location quick reply
        self.msg2 = self.create_outgoing_msg(joe, "Where?", quick_replies=["<location>Share location"])

        # msg with no quick replies
        self.msg3 = self.create_outgoing_msg(joe, "Hello")

        # msg that already has quickreplies set (should not be overwritten)
        self.msg4 = self.create_outgoing_msg(joe, "Existing", quick_replies=["Yes"])
        Msg.objects.filter(id=self.msg4.id).update(quickreplies=[{"type": "text", "text": "Already"}])

    def test_migration(self):
        self.msg1.refresh_from_db()
        self.assertEqual(
            [{"type": "text", "text": "Yes"}, {"type": "text", "text": "No", "extra": "Let's go!"}],
            self.msg1.quickreplies,
        )

        self.msg2.refresh_from_db()
        self.assertEqual(
            [{"type": "location", "text": "Share location"}],
            self.msg2.quickreplies,
        )

        self.msg3.refresh_from_db()
        self.assertIsNone(self.msg3.quickreplies)

        # msg4 already had quickreplies so should be unchanged
        self.msg4.refresh_from_db()
        self.assertEqual([{"type": "text", "text": "Already"}], self.msg4.quickreplies)

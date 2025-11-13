from datetime import datetime, timezone as tzone
from decimal import Decimal

from temba.msgs.models import Msg
from temba.tests import MigrationTest, cleanup, matchers
from temba.tests.dynamo import dynamo_scan_all
from temba.utils import dynamo


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


class BackfillMsgEventsTest(MigrationTest):
    app = "msgs"
    migrate_from = "0298_alter_broadcastmsgcount_count_alter_labelcount_count"
    migrate_to = "0299_backfill_msg_events"

    def setUpBeforeMigration(self, apps):
        contact = self.create_contact("Ann", uuid="40248365-230d-4a29-8dbc-c89e43dd3adf", phone="+16305550123")

        # incoming message with just text
        self.msg1 = self.create_incoming_msg(
            contact, "hi there", created_on=datetime(2025, 8, 11, 20, 36, 0, 0, tzinfo=tzone.utc)
        )

        # incoming message with external id and attachments
        self.msg2 = self.create_incoming_msg(
            contact,
            "",
            attachments=["image/jpeg:http://example.com/test.jpg"],
            created_on=datetime(2025, 8, 11, 20, 37, 0, 0, tzinfo=tzone.utc),
            external_id="ext-123",
        )

        # incoming message that has been deleted by a user
        self.msg3 = self.create_incoming_msg(
            contact,
            "Bad word",
            created_on=datetime(2025, 8, 11, 20, 38, 0, 0, tzinfo=tzone.utc),
            visibility=Msg.VISIBILITY_DELETED_BY_USER,
        )

        # incoming message that has been deleted by the contact
        self.msg4 = self.create_incoming_msg(
            contact,
            "Bad word",
            created_on=datetime(2025, 8, 11, 20, 39, 0, 0, tzinfo=tzone.utc),
            visibility=Msg.VISIBILITY_DELETED_BY_SENDER,
        )

        # outgoing message
        self.msg5 = self.create_outgoing_msg(
            contact,
            "Hello!",
            quick_replies=["Yes", "No"],
            created_on=datetime(2025, 8, 11, 20, 40, 0, 0, tzinfo=tzone.utc),
        )

        # outgoing message that was unsendable
        self.msg6 = self.create_outgoing_msg(
            contact,
            "Unsendable",
            created_on=datetime(2025, 8, 11, 20, 41, 0, 0, tzinfo=tzone.utc),
            failed_reason=Msg.FAILED_NO_DESTINATION,
        )

        # outgoing message that failed
        self.msg7 = self.create_outgoing_msg(
            contact,
            "Hi there?",
            created_on=datetime(2025, 8, 11, 20, 42, 0, 0, tzinfo=tzone.utc),
            failed_reason=Msg.FAILED_ERROR_LIMIT,
        )

        # outgoing IVR message
        self.msg8 = self.create_outgoing_msg(
            contact,
            "Press one",
            voice=True,
            created_on=datetime(2025, 8, 11, 20, 43, 0, 0, tzinfo=tzone.utc),
        )

        # message to deleted contact won't be backfilled
        deleted_contact = self.create_contact(
            "Deleted", uuid="1d48402f-df4c-44d8-b648-e0180f6a0dd2", phone="+16305550124", is_active=False
        )
        self.create_incoming_msg(
            deleted_contact, "hi there", created_on=datetime(2025, 8, 11, 20, 43, 0, 0, tzinfo=tzone.utc)
        )

    @cleanup(dynamodb=True)
    def test_migration(self):
        items = dynamo_scan_all(dynamo.HISTORY)
        self.assertEqual(
            [
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": f"evt#{self.msg1.uuid}",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "msg_received",
                        "created_on": "2025-08-11T20:36:00+00:00",
                        "msg": {
                            "text": "hi there",
                            "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                            "urn": "tel:+16305550123",
                        },
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": f"evt#{self.msg2.uuid}",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "msg_received",
                        "created_on": "2025-08-11T20:37:00+00:00",
                        "msg": {
                            "text": "",
                            "attachments": ["image/jpeg:http://example.com/test.jpg"],
                            "external_id": "ext-123",
                            "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                            "urn": "tel:+16305550123",
                        },
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": f"evt#{self.msg3.uuid}",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "msg_received",
                        "created_on": "2025-08-11T20:38:00+00:00",
                        "msg": {
                            "text": "Bad word",
                            "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                            "urn": "tel:+16305550123",
                        },
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": f"evt#{self.msg3.uuid}#del",
                    "OrgID": Decimal(self.org.id),
                    "Data": {"deleted_on": matchers.ISODatetime()},
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": f"evt#{self.msg4.uuid}",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "msg_received",
                        "created_on": "2025-08-11T20:39:00+00:00",
                        "msg": {
                            "text": "Bad word",
                            "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                            "urn": "tel:+16305550123",
                        },
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": f"evt#{self.msg4.uuid}#del",
                    "OrgID": Decimal(self.org.id),
                    "Data": {"deleted_on": matchers.ISODatetime(), "by_contact": True},
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": f"evt#{self.msg5.uuid}",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "msg_created",
                        "created_on": "2025-08-11T20:40:00+00:00",
                        "msg": {
                            "text": "Hello!",
                            "quick_replies": ["Yes", "No"],
                            "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                            "urn": "tel:+16305550123",
                        },
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": f"evt#{self.msg5.uuid}#sts",
                    "OrgID": Decimal(self.org.id),
                    "Data": {"status": "sent", "changed_on": matchers.ISODatetime()},
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": f"evt#{self.msg6.uuid}",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "msg_created",
                        "created_on": "2025-08-11T20:41:00+00:00",
                        "msg": {
                            "text": "Unsendable",
                            "channel": None,
                            "urn": None,
                            "unsendable_reason": "no_destination",
                        },
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": f"evt#{self.msg7.uuid}",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "msg_created",
                        "created_on": "2025-08-11T20:42:00+00:00",
                        "msg": {
                            "text": "Hi there?",
                            "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                            "urn": "tel:+16305550123",
                        },
                    },
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": f"evt#{self.msg7.uuid}#sts",
                    "OrgID": Decimal(self.org.id),
                    "Data": {"status": "failed", "changed_on": matchers.ISODatetime(), "reason": "error_limit"},
                },
                {
                    "PK": "con#40248365-230d-4a29-8dbc-c89e43dd3adf",
                    "SK": f"evt#{self.msg8.uuid}",
                    "OrgID": Decimal(self.org.id),
                    "Data": {
                        "type": "ivr_created",
                        "created_on": "2025-08-11T20:43:00+00:00",
                        "msg": {
                            "text": "Press one",
                            "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                            "urn": "tel:+16305550123",
                        },
                    },
                },
            ],
            items,
        )

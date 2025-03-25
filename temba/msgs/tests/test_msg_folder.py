from django.utils import timezone

from temba.flows.models import Flow, FlowRun, FlowSession
from temba.msgs.models import Msg, MsgFolder
from temba.orgs.tasks import squash_item_counts
from temba.schedules.models import Schedule
from temba.tests import TembaTest
from temba.utils import s3


class MsgFolderTest(TembaTest):
    def test_get_archive_query(self):
        tcs = (
            (
                MsgFolder.INBOX,
                "SELECT s.* FROM s3object s WHERE s.direction = 'in' AND s.visibility = 'visible' AND s.status = 'handled' AND s.flow IS NULL AND s.type != 'voice'",
            ),
            (
                MsgFolder.HANDLED,
                "SELECT s.* FROM s3object s WHERE s.direction = 'in' AND s.visibility = 'visible' AND s.status = 'handled' AND s.flow IS NOT NULL AND s.type != 'voice'",
            ),
            (
                MsgFolder.ARCHIVED,
                "SELECT s.* FROM s3object s WHERE s.direction = 'in' AND s.visibility = 'archived' AND s.status = 'handled' AND s.type != 'voice'",
            ),
            (
                MsgFolder.OUTBOX,
                "SELECT s.* FROM s3object s WHERE s.direction = 'out' AND s.visibility = 'visible' AND s.status IN ('initializing', 'queued', 'errored')",
            ),
            (
                MsgFolder.SENT,
                "SELECT s.* FROM s3object s WHERE s.direction = 'out' AND s.visibility = 'visible' AND s.status IN ('wired', 'sent', 'delivered', 'read')",
            ),
            (
                MsgFolder.FAILED,
                "SELECT s.* FROM s3object s WHERE s.direction = 'out' AND s.visibility = 'visible' AND s.status = 'failed'",
            ),
        )

        for folder, expected_select in tcs:
            select = s3.compile_select(where=folder.get_archive_query())
            self.assertEqual(expected_select, select, f"select s3 mismatch for {folder}")

    def test_get_counts(self):
        def assert_counts(org, expected: dict):
            self.assertEqual(MsgFolder.get_counts(org), expected)

        assert_counts(
            self.org,
            {
                MsgFolder.INBOX: 0,
                MsgFolder.HANDLED: 0,
                MsgFolder.ARCHIVED: 0,
                MsgFolder.OUTBOX: 0,
                MsgFolder.SENT: 0,
                MsgFolder.FAILED: 0,
                "scheduled": 0,
                "calls": 0,
            },
        )

        contact1 = self.create_contact("Bob", phone="0783835001")
        contact2 = self.create_contact("Jim", phone="0783835002")
        msg1 = self.create_incoming_msg(contact1, "Message 1")
        self.create_incoming_msg(contact1, "Message 2")
        msg3 = self.create_incoming_msg(contact1, "Message 3")
        msg4 = self.create_incoming_msg(contact1, "Message 4")
        self.create_broadcast(self.editor, {"eng": {"text": "Broadcast 2"}}, contacts=[contact1, contact2], status="P")
        self.create_broadcast(
            self.editor,
            {"eng": {"text": "Broadcast 2"}},
            contacts=[contact1, contact2],
            schedule=Schedule.create(self.org, timezone.now(), Schedule.REPEAT_DAILY),
        )
        ivr_flow = self.create_flow("IVR", flow_type=Flow.TYPE_VOICE)
        call1 = self.create_incoming_call(ivr_flow, contact1)
        self.create_incoming_call(ivr_flow, contact2)

        assert_counts(
            self.org,
            {
                MsgFolder.INBOX: 4,
                MsgFolder.HANDLED: 0,
                MsgFolder.ARCHIVED: 0,
                MsgFolder.OUTBOX: 0,
                MsgFolder.SENT: 2,
                MsgFolder.FAILED: 0,
                "scheduled": 1,
                "calls": 2,
            },
        )

        msg3.archive()

        bcast1 = self.create_broadcast(
            self.editor,
            {"eng": {"text": "Broadcast 1"}},
            contacts=[contact1, contact2],
            msg_status=Msg.STATUS_INITIALIZING,
        )
        msg5, msg6 = tuple(Msg.objects.filter(broadcast=bcast1))

        self.create_broadcast(
            self.editor,
            {"eng": {"text": "Broadcast 3"}},
            contacts=[contact1],
            schedule=Schedule.create(self.org, timezone.now(), Schedule.REPEAT_DAILY),
        )

        assert_counts(
            self.org,
            {
                MsgFolder.INBOX: 3,
                MsgFolder.HANDLED: 0,
                MsgFolder.ARCHIVED: 1,
                MsgFolder.OUTBOX: 2,
                MsgFolder.SENT: 2,
                MsgFolder.FAILED: 0,
                "scheduled": 2,
                "calls": 2,
            },
        )

        msg1.archive()
        msg3.delete()  # deleting an archived msg
        msg4.delete()  # deleting a visible msg
        msg5.status = "F"
        msg5.save(update_fields=("status",))
        msg6.status = "S"
        msg6.save(update_fields=("status",))
        FlowRun.objects.all().delete()
        FlowSession.objects.all().delete()
        call1.delete()

        assert_counts(
            self.org,
            {
                MsgFolder.INBOX: 1,
                MsgFolder.HANDLED: 0,
                MsgFolder.ARCHIVED: 1,
                MsgFolder.OUTBOX: 0,
                MsgFolder.SENT: 3,
                MsgFolder.FAILED: 1,
                "scheduled": 2,
                "calls": 1,
            },
        )

        msg1.restore()
        msg5.status = "F"  # already failed
        msg5.save(update_fields=("status",))
        msg6.status = "D"
        msg6.save(update_fields=("status",))

        assert_counts(
            self.org,
            {
                MsgFolder.INBOX: 2,
                MsgFolder.HANDLED: 0,
                MsgFolder.ARCHIVED: 0,
                MsgFolder.OUTBOX: 0,
                MsgFolder.SENT: 3,
                MsgFolder.FAILED: 1,
                "scheduled": 2,
                "calls": 1,
            },
        )

        self.assertEqual(self.org.counts.count(), 25)

        # squash our counts
        squash_item_counts()

        assert_counts(
            self.org,
            {
                MsgFolder.INBOX: 2,
                MsgFolder.HANDLED: 0,
                MsgFolder.ARCHIVED: 0,
                MsgFolder.OUTBOX: 0,
                MsgFolder.SENT: 3,
                MsgFolder.FAILED: 1,
                "scheduled": 2,
                "calls": 1,
            },
        )

        # we should only have one count per folder with non-zero count
        self.assertEqual(self.org.counts.count(), 5)

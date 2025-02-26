from datetime import datetime, timezone as tzone

from django.utils import timezone

from temba.flows.models import FlowRun, FlowSession
from temba.flows.tasks import trim_flow_sessions
from temba.tests import TembaTest
from temba.utils.uuid import uuid4


class FlowSessionTest(TembaTest):
    def test_trim(self):
        contact = self.create_contact("Ben Haggerty", phone="+250788123123")
        flow = self.create_flow("Test")

        # create some runs that have sessions
        session1 = FlowSession.objects.create(
            uuid=uuid4(),
            contact=contact,
            output_url="http://sessions.com/123.json",
            status=FlowSession.STATUS_WAITING,
        )
        session2 = FlowSession.objects.create(
            uuid=uuid4(),
            contact=contact,
            output_url="http://sessions.com/234.json",
            status=FlowSession.STATUS_WAITING,
        )
        session3 = FlowSession.objects.create(
            uuid=uuid4(),
            contact=contact,
            output_url="http://sessions.com/345.json",
            status=FlowSession.STATUS_WAITING,
        )
        run1 = FlowRun.objects.create(
            org=self.org, flow=flow, contact=contact, session=session1, status=FlowRun.STATUS_WAITING
        )
        run2 = FlowRun.objects.create(
            org=self.org, flow=flow, contact=contact, session=session2, status=FlowRun.STATUS_WAITING
        )
        run3 = FlowRun.objects.create(
            org=self.org, flow=flow, contact=contact, session=session3, status=FlowRun.STATUS_WAITING
        )

        # create an IVR call with session
        call = self.create_incoming_call(flow, contact)
        run4 = FlowRun.objects.get(session_uuid=call.session_uuid)

        self.assertIsNotNone(run1.session)
        self.assertIsNotNone(run2.session)
        self.assertIsNotNone(run3.session)
        self.assertIsNotNone(run4.session)

        # end run1 and run4's sessions in the past
        run1.status = FlowRun.STATUS_COMPLETED
        run1.exited_on = datetime(2015, 9, 15, 0, 0, 0, 0, tzone.utc)
        run1.save(update_fields=("status", "exited_on"))
        run1.session.status = FlowSession.STATUS_COMPLETED
        run1.session.ended_on = datetime(2015, 9, 15, 0, 0, 0, 0, tzone.utc)
        run1.session.save(update_fields=("status", "ended_on"))

        run4.status = FlowRun.STATUS_INTERRUPTED
        run4.exited_on = datetime(2015, 9, 15, 0, 0, 0, 0, tzone.utc)
        run4.save(update_fields=("status", "exited_on"))
        run4.session.status = FlowSession.STATUS_INTERRUPTED
        run4.session.ended_on = datetime(2015, 9, 15, 0, 0, 0, 0, tzone.utc)
        run4.session.save(update_fields=("status", "ended_on"))

        # end run2's session now
        run2.status = FlowRun.STATUS_EXPIRED
        run2.exited_on = timezone.now()
        run2.save(update_fields=("status", "exited_on"))
        run4.session.status = FlowSession.STATUS_COMPLETED
        run2.session.ended_on = timezone.now()
        run2.session.save(update_fields=("status", "ended_on"))

        trim_flow_sessions()

        run1, run2, run3, run4 = FlowRun.objects.order_by("id")

        self.assertIsNone(run1.session)
        self.assertIsNotNone(run2.session)  # ended too recently to be deleted
        self.assertIsNotNone(run3.session)  # never ended
        self.assertIsNone(run4.session)

        # only sessions for run2 and run3 are left
        self.assertEqual(FlowSession.objects.count(), 2)

from datetime import timedelta

from django.utils import timezone

from temba.channels.models import ChannelEvent
from temba.ivr.models import Call
from temba.mailroom.events import Event
from temba.msgs.models import Msg
from temba.tests import TembaTest, matchers
from temba.tests.engine import MockSessionWriter
from temba.tickets.models import TicketEvent


class EventTest(TembaTest):
    def test_from_msg(self):
        contact1 = self.create_contact("Jim", phone="0979111111")
        contact2 = self.create_contact("Bob", phone="0979222222")

        # create msg that is too old to still have logs
        msg_in = self.create_incoming_msg(
            contact1,
            "Hello",
            external_id="12345",
            attachments=["image:http://a.jpg"],
            created_on=timezone.now() - timedelta(days=15),
        )

        self.assertEqual(
            {
                "type": "msg_received",
                "created_on": matchers.ISODatetime(),
                "msg": {
                    "uuid": str(msg_in.uuid),
                    "id": msg_in.id,
                    "urn": "tel:+250979111111",
                    "text": "Hello",
                    "attachments": ["image:http://a.jpg"],
                    "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                    "external_id": "12345",
                },
                "msg_type": "T",
                "visibility": "V",
                "logs_url": None,
            },
            Event.from_msg(self.org, self.admin, msg_in),
        )

        msg_in.visibility = Msg.VISIBILITY_DELETED_BY_USER
        msg_in.save(update_fields=("visibility",))

        self.assertEqual(
            {
                "type": "msg_received",
                "created_on": matchers.ISODatetime(),
                "msg": {
                    "uuid": str(msg_in.uuid),
                    "id": msg_in.id,
                    "urn": "tel:+250979111111",
                    "text": "",
                    "attachments": [],
                    "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                    "external_id": "12345",
                },
                "msg_type": "T",
                "visibility": "D",
                "logs_url": None,
            },
            Event.from_msg(self.org, self.admin, msg_in),
        )

        msg_in.visibility = Msg.VISIBILITY_DELETED_BY_SENDER
        msg_in.save(update_fields=("visibility",))

        self.assertEqual(
            {
                "type": "msg_received",
                "created_on": matchers.ISODatetime(),
                "msg": {
                    "uuid": str(msg_in.uuid),
                    "id": msg_in.id,
                    "urn": "tel:+250979111111",
                    "text": "",
                    "attachments": [],
                    "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                    "external_id": "12345",
                },
                "msg_type": "T",
                "visibility": "X",
                "logs_url": None,
            },
            Event.from_msg(self.org, self.admin, msg_in),
        )

        msg_out = self.create_outgoing_msg(
            contact1, "Hello", channel=self.channel, status="E", quick_replies=["yes", "no"], created_by=self.agent
        )

        self.assertEqual(
            {
                "type": "msg_created",
                "created_on": matchers.ISODatetime(),
                "msg": {
                    "uuid": str(msg_out.uuid),
                    "id": msg_out.id,
                    "urn": "tel:+250979111111",
                    "text": "Hello",
                    "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                    "quick_replies": ["yes", "no"],
                },
                "created_by": {
                    "id": self.agent.id,
                    "email": "agent@textit.com",
                    "first_name": "Agnes",
                    "last_name": "",
                },
                "optin": None,
                "status": "E",
                "logs_url": f"/channels/channel/logs/{str(self.channel.uuid)}/msg/{msg_out.id}/",
            },
            Event.from_msg(self.org, self.admin, msg_out),
        )

        msg_out = self.create_outgoing_msg(contact1, "Hello", status="F", failed_reason=Msg.FAILED_NO_DESTINATION)

        self.assertEqual(
            {
                "type": "msg_created",
                "created_on": matchers.ISODatetime(),
                "msg": {
                    "uuid": str(msg_out.uuid),
                    "id": msg_out.id,
                    "urn": None,
                    "text": "Hello",
                    "channel": None,
                },
                "created_by": None,
                "optin": None,
                "status": "F",
                "failed_reason": "D",
                "failed_reason_display": "No suitable channel found",
                "logs_url": None,
            },
            Event.from_msg(self.org, self.admin, msg_out),
        )

        ivr_out = self.create_outgoing_msg(contact1, "Hello", voice=True)

        self.assertEqual(
            {
                "type": "ivr_created",
                "created_on": matchers.ISODatetime(),
                "msg": {
                    "uuid": str(ivr_out.uuid),
                    "id": ivr_out.id,
                    "urn": "tel:+250979111111",
                    "text": "Hello",
                    "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                },
                "created_by": None,
                "status": "S",
                "logs_url": f"/channels/channel/logs/{str(self.channel.uuid)}/msg/{ivr_out.id}/",
            },
            Event.from_msg(self.org, self.admin, ivr_out),
        )

        bcast = self.create_broadcast(self.admin, {"und": {"text": "Hi there"}}, contacts=[contact1, contact2])
        msg_out2 = bcast.msgs.filter(contact=contact1).get()

        self.assertEqual(
            {
                "type": "broadcast_created",
                "created_on": matchers.ISODatetime(),
                "translations": {"und": {"text": "Hi there"}},
                "base_language": "und",
                "msg": {
                    "uuid": str(msg_out2.uuid),
                    "id": msg_out2.id,
                    "urn": "tel:+250979111111",
                    "text": "Hi there",
                    "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                },
                "created_by": {
                    "id": self.admin.id,
                    "email": "admin@textit.com",
                    "first_name": "Andy",
                    "last_name": "",
                },
                "optin": None,
                "status": "S",
                "recipient_count": 2,
                "logs_url": f"/channels/channel/logs/{str(self.channel.uuid)}/msg/{msg_out2.id}/",
            },
            Event.from_msg(self.org, self.admin, msg_out2),
        )

        # create a broadcast that was sent with an opt-in
        optin = self.create_optin("Polls")
        bcast2 = self.create_broadcast(
            self.admin, {"und": {"text": "Hi there"}}, contacts=[contact1, contact2], optin=optin
        )
        msg_out3 = bcast2.msgs.filter(contact=contact1).get()

        self.assertEqual(
            {
                "type": "broadcast_created",
                "created_on": matchers.ISODatetime(),
                "translations": {"und": {"text": "Hi there"}},
                "base_language": "und",
                "msg": {
                    "uuid": str(msg_out3.uuid),
                    "id": msg_out3.id,
                    "urn": "tel:+250979111111",
                    "text": "Hi there",
                    "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                },
                "created_by": {
                    "id": self.admin.id,
                    "email": "admin@textit.com",
                    "first_name": "Andy",
                    "last_name": "",
                },
                "optin": {"uuid": str(optin.uuid), "name": "Polls"},
                "status": "S",
                "recipient_count": 2,
                "logs_url": f"/channels/channel/logs/{str(self.channel.uuid)}/msg/{msg_out3.id}/",
            },
            Event.from_msg(self.org, self.admin, msg_out3),
        )

        # create a message that was an opt-in request
        msg_out4 = self.create_optin_request(contact1, self.channel, optin)
        self.assertEqual(
            {
                "type": "optin_requested",
                "created_on": matchers.ISODatetime(),
                "optin": {"uuid": str(optin.uuid), "name": "Polls"},
                "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                "urn": "tel:+250979111111",
                "created_by": None,
                "status": "S",
                "logs_url": f"/channels/channel/logs/{str(self.channel.uuid)}/msg/{msg_out4.id}/",
            },
            Event.from_msg(self.org, self.admin, msg_out4),
        )

    def test_from_channel_event(self):
        self.create_contact("Jim", phone="+250979111111")

        event1 = self.create_channel_event(
            self.channel, "tel:+250979111111", ChannelEvent.TYPE_CALL_IN, extra={"duration": 5}
        )

        self.assertEqual(
            {
                "type": "channel_event",
                "created_on": matchers.ISODatetime(),
                "event": {
                    "type": "mo_call",
                    "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                    "duration": 5,
                },
                "channel_event_type": "mo_call",  # deprecated
                "duration": 5,  # deprecated
            },
            Event.from_channel_event(self.org, self.admin, event1),
        )

        optin = self.create_optin("Polls")
        event2 = self.create_channel_event(
            self.channel,
            "tel:+250979111111",
            ChannelEvent.TYPE_OPTIN,
            optin=optin,
            extra={"title": "Polls", "payload": str(optin.id)},
        )

        self.assertEqual(
            {
                "type": "channel_event",
                "created_on": matchers.ISODatetime(),
                "event": {
                    "type": "optin",
                    "channel": {"uuid": str(self.channel.uuid), "name": "Test Channel"},
                    "optin": {"uuid": str(optin.uuid), "name": "Polls"},
                },
                "channel_event_type": "optin",  # deprecated
                "duration": None,  # deprecated
            },
            Event.from_channel_event(self.org, self.admin, event2),
        )

    def test_from_flow_run(self):
        contact = self.create_contact("Jim", phone="0979111111")
        flow = self.get_flow("color_v13")
        nodes = flow.get_definition()["nodes"]
        run = (
            MockSessionWriter(contact, flow)
            .visit(nodes[0])
            .send_msg("What is your favorite color?", self.channel)
            .wait()
            .save()
        )[0]

        self.assertEqual(
            {
                "type": "flow_entered",
                "created_on": matchers.ISODatetime(),
                "flow": {"uuid": str(flow.uuid), "name": "Colors"},
                "logs_url": None,
            },
            Event.from_flow_run(self.org, self.admin, run),
        )

        # customer support get access to logs
        self.assertEqual(
            {
                "type": "flow_entered",
                "created_on": matchers.ISODatetime(),
                "flow": {"uuid": str(flow.uuid), "name": "Colors"},
                "logs_url": f"/flowsession/json/{run.session_uuid}/",
            },
            Event.from_flow_run(self.org, self.customer_support, run),
        )

    def test_from_ticket_event(self):
        contact = self.create_contact("Jim", phone="0979111111")
        ticket = self.create_ticket(contact)

        # event with a user
        event1 = TicketEvent.objects.create(
            org=self.org,
            contact=contact,
            ticket=ticket,
            event_type=TicketEvent.TYPE_NOTE_ADDED,
            created_by=self.agent,
            note="this is important",
        )

        self.assertEqual(
            {
                "type": "ticket_note_added",
                "note": "this is important",
                "topic": None,
                "assignee": None,
                "ticket": {
                    "uuid": str(ticket.uuid),
                    "opened_on": matchers.ISODatetime(),
                    "closed_on": None,
                    "status": "O",
                    "topic": {"uuid": str(self.org.default_ticket_topic.uuid), "name": "General"},
                },
                "created_on": matchers.ISODatetime(),
                "created_by": {
                    "id": self.agent.id,
                    "first_name": "Agnes",
                    "last_name": "",
                    "email": "agent@textit.com",
                },
            },
            Event.from_ticket_event(self.org, self.admin, event1),
        )

        # event without a user
        event2 = TicketEvent.objects.create(
            org=self.org, contact=contact, ticket=ticket, event_type=TicketEvent.TYPE_CLOSED
        )

        self.assertEqual(
            {
                "type": "ticket_closed",
                "note": None,
                "topic": None,
                "assignee": None,
                "ticket": {
                    "uuid": str(ticket.uuid),
                    "opened_on": matchers.ISODatetime(),
                    "closed_on": None,
                    "status": "O",
                    "topic": {"uuid": str(self.org.default_ticket_topic.uuid), "name": "General"},
                },
                "created_on": matchers.ISODatetime(),
                "created_by": None,
            },
            Event.from_ticket_event(self.org, self.admin, event2),
        )

    def test_from_ivr_call(self):
        flow = self.create_flow("IVR", flow_type="V")
        contact = self.create_contact("Jim", phone="0979111111")

        # create call that is too old to still have logs
        call1 = self.create_incoming_call(
            flow, contact, status=Call.STATUS_IN_PROGRESS, created_on=timezone.now() - timedelta(days=15)
        )

        # and one that will have logs
        call2 = self.create_incoming_call(flow, contact, status=Call.STATUS_ERRORED, error_reason=Call.ERROR_BUSY)

        self.assertEqual(
            {
                "type": "call_started",
                "status": "I",
                "status_display": "In Progress",
                "created_on": matchers.ISODatetime(),
                "logs_url": None,
            },
            Event.from_ivr_call(self.org, self.admin, call1),
        )

        self.assertEqual(
            {
                "type": "call_started",
                "status": "E",
                "status_display": "Errored (Busy)",
                "created_on": matchers.ISODatetime(),
                "logs_url": None,  # user can't see logs
            },
            Event.from_ivr_call(self.org, self.agent, call2),
        )
        self.assertEqual(
            {
                "type": "call_started",
                "status": "E",
                "status_display": "Errored (Busy)",
                "created_on": matchers.ISODatetime(),
                "logs_url": f"/channels/channel/logs/{call2.channel.uuid}/call/{call2.id}/",
            },
            Event.from_ivr_call(self.org, self.admin, call2),
        )

import base64
from datetime import timedelta

import iso8601
from boto3.dynamodb.types import Binary

from django.utils import timezone

from temba.mailroom.events import Event
from temba.msgs.models import Msg
from temba.tests import TembaTest, cleanup, matchers


class EventTest(TembaTest):
    def test_from_item(self):
        contact = self.create_contact("Jim", phone="+593979111111")
        event = Event._from_item(
            contact,
            {
                "PK": "con#6393abc0-283d-4c9b-a1b3-641a035c34bf",
                "SK": "evt#01969b47-2c93-76f8-8f41-6b2d9f33d623",
                "OrgID": self.org.id,
                "TTL": 1747571456,
                "Data": {
                    "_user_id": self.admin.id,
                    "type": "contact_field_changed",
                    "created_on": "2025-05-04T12:30:56.123456789Z",
                    "field": {"key": "age", "name": "Age"},
                    "value": {"text": "44"},
                },
            },
        )
        self.assertEqual(
            {
                "uuid": "01969b47-2c93-76f8-8f41-6b2d9f33d623",
                "type": "contact_field_changed",
                "created_on": "2025-05-04T12:30:56.123456789Z",
                "field": {"key": "age", "name": "Age"},
                "value": {"text": "44"},
                "_user_id": self.admin.id,
            },
            event,
        )

        event = Event._from_item(
            contact,
            {
                "PK": "con#6393abc0-283d-4c9b-a1b3-641a035c34bf",
                "SK": "evt#01969b47-672b-76f8-bebe-b4a1f677cf4c",
                "OrgID": self.org.id,
                "TTL": 1747571471,
                "DataGZ": Binary(
                    base64.b64decode(
                        "H4sIAAAAAAAA/6RVTW/cNhD9KwKvFVt+U9KpToC0RdGLm0PiNBCG5HBDRCu5EmXHCfa/F9TKGzdNiwAFdJBI4s17bx5Hn8i6pkA6wnhrWqcsNVY4ak1sqEOH1Cng0Vjro/KkJvnhFklHFlyWNI19ntPhgDMGUhM/I2QM/TSSjggmNGWaMvWSi07yjvPvuZBKG9u0N6QmS8bbfq/tpXLG20AjMEOVNpK2AiQNRjXgjHLeO1KTOEz3pLswdtZHFhpJI/ctVZx72poYqNecg/IRGlNojXAsjK/xkJY8Q07TWL0oSKea+GnM4PNCujcX2EawqFshqZSmwHpDnfSBQtTWeuaCcs1n2GeTI6e3NcEPfliLJQvpPp1qMq9jv6zHI8wPhfJeaHv9u02MUcYp4y8Z67anmBMTDqEgEfA53W2k+zy9x7GsZfyQSUdevXpFX79+TW9uboqWmOYl92dalzPPcCx7M9z3ochPZw777i/VkO6wSmN1gAXcVI4uGfKGsL+Q63sYA1R/rIxJrH5NBxhS9Tzlh5KGM86/HzmdanKYp/X2bPFu2u/rfIcP1dUaEo4eSf3ovQAIgkdDJXOWKuE1dcFGyp0VzHOtGm7Jqb4APSlV/YZHh/PyGSzYGFVjBW2FbKjSItI2yIaKqHUTEZoW2da7cnrPZk0GGA8rHAo6jgdSFpbcL4jjpWNm65h4yXXHVMf0zZM44Fj9DOVKbP4UD9eFdOc2FqE5HfHjNJazV0eck4cfflrhAf5c01CozyVAb0jGofuOC2a01lxwUTIBHt00ve84F0JKpbQ2xtqmhPEIachT53D88Qj+/YDHad6q3aeccS4b/btHWm8vDjlojYs2UucFUNVYScF6S4VWgbfCeoVyi9Z+8XaRV8NQXfm8hf2C1XhQyrOW2pYHqrQE2tq2pWBZCFIyKZnZoojLOuQt2yKCz9O8XQrIeJjKXSFlkuxf/TB5GNJHDPv6f04YYfcJU/qBH/IMpBvXYahJGm/XfIbYJYgX59I1GaeAj3MoaudaZ4Fap5Eq7SVtIkNquFPYagyRSVKTOxjWAiKVkcoIpYzUQm9Gwd00p4y9n4Z/CLs+T8mvabv+hgEqxLfLe7HzqJ5vPP6XyjLcT6evZfnLPwfncv9ztJ45KhhXIXhrWauKOe/SkqfzOLyFGcfcfwnAdCPPAIA20tg4oaRXbYya1ARGjwVhIR1/8tUvafTY7yaw0+mvAAAA//+R/as+0wYAAA=="
                    )
                ),
            },
        )
        self.assertEqual("01969b47-672b-76f8-bebe-b4a1f677cf4c", event["uuid"])
        self.assertEqual("session_triggered", event["type"])

    @cleanup(dynamodb=True)
    def test_get_by_contact(self):
        contact = self.create_contact("Jim", phone="+593979111111")
        self.write_history_event(
            contact,
            {
                "uuid": "019880eb-e422-7d67-993f-cdec64636001",  # 1: (last char is 1...5)
                "type": "contact_language_changed",
                "created_on": "2025-08-06T19:46:39.778889794Z",
                "language": "spa",
            },
        )
        self.write_history_event(
            contact,
            {
                "uuid": "019880eb-e488-7652-beb6-0051d9cd6002",  # 2
                "type": "contact_field_changed",
                "created_on": "2025-08-06T19:46:39.880430294Z",
                "field": {"key": "age", "name": "Age"},
                "value": {"text": "44"},
            },
        )
        self.write_history_event(
            contact,
            {
                "uuid": "019880eb-e488-76d2-a8c4-872e95772003",  # 3
                "type": "contact_groups_changed",
                "created_on": "2025-08-06T19:46:39.880448169Z",  # less than 1ms after previous event
                "groups_added": [{"uuid": "fac9a1bd-6db5-4efb-8899-097acda87f96", "name": "Youth"}],
            },
        )
        self.write_history_event(
            contact,
            {
                "uuid": "019880eb-e4f1-761b-bc99-750003cf8004",  # 4
                "type": "contact_name_changed",
                "created_on": "2025-08-06T19:46:39.985439836Z",
                "name": "Bob",
            },
        )
        self.write_history_event(
            contact,
            {
                "uuid": "019880eb-e555-7ce9-9ea3-95bf693ee005",  # 5
                "type": "contact_name_changed",
                "created_on": "2025-08-06T19:46:40.085871336Z",
                "name": "Robert",
            },
        )

        self.write_history_event(
            contact,
            {
                "uuid": "01988abd-1dad-7309-b8b4-adb8380ef531",  # 6
                "type": "contact_status_changed",  # not a supported type for now
                "created_on": "2025-08-06T19:47:40.085871336Z",
                "status": "blocked",
            },
        )

        def assert_fetched(after, before, limit, expected: list):
            fetched = Event.get_by_contact(contact, after=after, before=before, ticket_uuid=None, limit=limit)
            self.assertEqual(expected, [e["uuid"][-3:] for e in fetched])

        assert_fetched(
            iso8601.parse_date("2025-08-06T18:46:40.085871336Z"),
            iso8601.parse_date("2025-08-06T19:46:40.085871336Z"),  # event 5 (exclusive)
            5,
            ["004", "003", "002", "001"],
        )

        assert_fetched(
            iso8601.parse_date("2025-08-06T18:46:40.085871336Z"),
            iso8601.parse_date("2025-08-06T19:46:40.085871336Z"),  # event 5 (exclusive)
            3,
            ["004", "003", "002"],
        )

        assert_fetched(
            iso8601.parse_date("2025-08-06T19:46:39.880430294Z"),  # event 2 (inclusive)
            iso8601.parse_date("2025-08-06T19:46:40.085871336Z"),  # event 5 (exclusive)
            5,
            ["004", "003", "002"],
        )

        assert_fetched(
            iso8601.parse_date("2025-08-06T19:46:40.085871336Z"),
            iso8601.parse_date("2025-08-06T18:46:40.085871336Z"),  # after < before
            5,
            [],
        )

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
                "uuid": str(msg_in.uuid),
                "type": "msg_received",
                "created_on": matchers.ISODatetime(),
                "msg": {
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
                "uuid": str(msg_in.uuid),
                "type": "msg_received",
                "created_on": matchers.ISODatetime(),
                "msg": {
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
                "uuid": str(msg_in.uuid),
                "type": "msg_received",
                "created_on": matchers.ISODatetime(),
                "msg": {
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
                "uuid": str(msg_out.uuid),
                "type": "msg_created",
                "created_on": matchers.ISODatetime(),
                "msg": {
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
                "uuid": str(msg_out.uuid),
                "type": "msg_created",
                "created_on": matchers.ISODatetime(),
                "msg": {
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
                "uuid": str(ivr_out.uuid),
                "type": "ivr_created",
                "created_on": matchers.ISODatetime(),
                "msg": {
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
                "uuid": str(msg_out2.uuid),
                "type": "broadcast_created",
                "created_on": matchers.ISODatetime(),
                "translations": {"und": {"text": "Hi there"}},
                "base_language": "und",
                "msg": {
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
                "uuid": str(msg_out3.uuid),
                "type": "broadcast_created",
                "created_on": matchers.ISODatetime(),
                "translations": {"und": {"text": "Hi there"}},
                "base_language": "und",
                "msg": {
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
                "uuid": str(msg_out4.uuid),
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

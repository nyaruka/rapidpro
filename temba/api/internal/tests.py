from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from temba.ai.models import LLM
from temba.ai.types.anthropic.type import AnthropicType
from temba.ai.types.openai.type import OpenAIType
from temba.api.tests.mixins import APITestMixin
from temba.contacts.models import ContactExport
from temba.msgs.models import Msg
from temba.notifications.types import ExportFinishedNotificationType
from temba.templates.models import TemplateTranslation
from temba.tests import TembaTest, matchers
from temba.tickets.models import Shortcut, TicketExport

NUM_BASE_QUERIES = 3  # number of queries required for any request (internal API is session only)


class EndpointsTest(APITestMixin, TembaTest):
    def test_locations(self):
        endpoint_url = reverse("api.internal.locations") + ".json"

        self.assertGetNotPermitted(endpoint_url, [None])
        self.assertPostNotAllowed(endpoint_url)
        self.assertDeleteNotAllowed(endpoint_url)

        # no country, no results
        self.assertGet(endpoint_url + "?level=state", [self.agent], results=[])

        self.setUpLocations()

        self.assertGet(
            endpoint_url + "?level=state",
            [self.agent],
            results=[
                {"osm_id": "171591", "name": "Eastern Province", "path": "Rwanda > Eastern Province"},
                {"osm_id": "1708283", "name": "Kigali City", "path": "Rwanda > Kigali City"},
            ],
            num_queries=NUM_BASE_QUERIES + 2,
        )
        self.assertGet(
            endpoint_url + "?level=district",
            [self.editor],
            results=[
                {"osm_id": "R1711131", "name": "Gatsibo", "path": "Rwanda > Eastern Province > Gatsibo"},
                {"osm_id": "1711163", "name": "Kayônza", "path": "Rwanda > Eastern Province > Kayônza"},
                {"osm_id": "3963734", "name": "Nyarugenge", "path": "Rwanda > Kigali City > Nyarugenge"},
                {"osm_id": "1711142", "name": "Rwamagana", "path": "Rwanda > Eastern Province > Rwamagana"},
            ],
        )

        # can query on path
        self.assertGet(
            endpoint_url + "?level=district&query=ga",
            [self.editor],
            results=[
                {"osm_id": "R1711131", "name": "Gatsibo", "path": "Rwanda > Eastern Province > Gatsibo"},
                {"osm_id": "3963734", "name": "Nyarugenge", "path": "Rwanda > Kigali City > Nyarugenge"},
                {"osm_id": "1711142", "name": "Rwamagana", "path": "Rwanda > Eastern Province > Rwamagana"},
            ],
        )

        # missing or invalid level, no results
        self.assertGet(endpoint_url + "?level=hood", [self.agent], results=[])
        self.assertGet(endpoint_url, [self.agent], results=[])

    def test_messages(self):
        endpoint_url = reverse("api.internal.messages") + ".json"

        self.assertGetNotPermitted(endpoint_url, [None, self.agent])
        self.assertPostNotAllowed(endpoint_url)
        self.assertDeleteNotAllowed(endpoint_url)

        contact1 = self.create_contact("Ann", phone="+1234567001")
        contact2 = self.create_contact("Bob", phone="+1234567002")
        label = self.create_label("Spam")

        # inbox messages (incoming, handled, visible, no flow)
        msg1 = self.create_incoming_msg(contact1, "Hello there")
        msg2 = self.create_incoming_msg(contact2, "Look at this", attachments=["image/jpeg:https://example.com/a.jpg"])
        msg2.labels.add(label)

        # a message in another folder shouldn't appear in the inbox
        archived = self.create_incoming_msg(contact1, "Archived", visibility=Msg.VISIBILITY_ARCHIVED)

        msg1_logs_url = reverse("channels.channel_logs_read", args=[self.channel.uuid, "msg", msg1.uuid])
        msg2_logs_url = reverse("channels.channel_logs_read", args=[self.channel.uuid, "msg", msg2.uuid])

        # admin has `channels.channel_logs` so as_json resolves logs_url to a real path
        self.assertGet(
            endpoint_url,
            [self.admin],
            results=[
                {
                    "id": msg2.id,
                    "type": "text",
                    "contact": {"uuid": str(contact2.uuid), "name": "Bob"},
                    "text": "Look at this",
                    "attachments": ["image/jpeg:https://example.com/a.jpg"],
                    "labels": [{"uuid": str(label.uuid), "name": "Spam"}],
                    "flow": None,
                    "created_on": matchers.ISODatetime(),
                    "logs_url": msg2_logs_url,
                },
                {
                    "id": msg1.id,
                    "type": "text",
                    "contact": {"uuid": str(contact1.uuid), "name": "Ann"},
                    "text": "Hello there",
                    "attachments": [],
                    "labels": [],
                    "flow": None,
                    "created_on": matchers.ISODatetime(),
                    "logs_url": msg1_logs_url,
                },
            ],
        )

        # editor lacks `channels.channel_logs` so logs_url is gated to None
        self.assertGet(
            endpoint_url,
            [self.editor],
            results=[
                {
                    "id": msg2.id,
                    "type": "text",
                    "contact": {"uuid": str(contact2.uuid), "name": "Bob"},
                    "text": "Look at this",
                    "attachments": ["image/jpeg:https://example.com/a.jpg"],
                    "labels": [{"uuid": str(label.uuid), "name": "Spam"}],
                    "flow": None,
                    "created_on": matchers.ISODatetime(),
                    "logs_url": None,
                },
                {
                    "id": msg1.id,
                    "type": "text",
                    "contact": {"uuid": str(contact1.uuid), "name": "Ann"},
                    "text": "Hello there",
                    "attachments": [],
                    "labels": [],
                    "flow": None,
                    "created_on": matchers.ISODatetime(),
                    "logs_url": None,
                },
            ],
        )

        # backdated past the channel-log retention window: logs_url is gated to None even for admin.
        # `created_on` is passed at insert time because a DB trigger forbids changing it after the fact.
        old_msg = self.create_incoming_msg(contact1, "Older", created_on=timezone.now() - timedelta(days=30))
        response = self.assertGet(endpoint_url + f"?search={old_msg.text}", [self.admin], results=[old_msg])
        self.assertIsNone(response.json()["results"][0]["logs_url"])

        # inactive channel: logs_url is gated to None
        live_msg = self.create_incoming_msg(contact1, "Liveone")
        self.channel.is_active = False
        self.channel.save(update_fields=("is_active",))
        try:
            response = self.assertGet(endpoint_url + f"?search={live_msg.text}", [self.admin], results=[live_msg])
            self.assertIsNone(response.json()["results"][0]["logs_url"])
        finally:
            self.channel.is_active = True
            self.channel.save(update_fields=("is_active",))

        # anonymous org with an unnamed contact: as_json returns the masked ref (not the urn) for the contact name
        anon_contact = self.create_contact("", phone="+1234567099")
        anon_msg = self.create_incoming_msg(anon_contact, "Anonymous")
        with self.anonymous(self.org):
            response = self.assertGet(endpoint_url + f"?search={anon_msg.text}", [self.admin], results=[anon_msg])
            masked_name = response.json()["results"][0]["contact"]["name"]
            self.assertNotIn("1234567099", masked_name)
            self.assertEqual(anon_contact.ref, masked_name)

        # can select a different folder
        self.assertGet(endpoint_url + "?folder=archived", [self.admin], results=[archived])

        # an unknown folder returns nothing
        self.assertGet(endpoint_url + "?folder=nope", [self.admin], results=[])

        # ?folder=sent orders by sent_on rather than created_on
        sent_old = self.create_outgoing_msg(contact1, "Old reply", sent_on=timezone.now() - timedelta(hours=2))
        sent_new = self.create_outgoing_msg(contact1, "Newer reply", sent_on=timezone.now() - timedelta(minutes=5))
        self.assertGet(endpoint_url + "?folder=sent", [self.admin], results=[sent_new, sent_old])

        # ?label=<uuid> filters to that label's visible messages
        self.assertGet(endpoint_url + f"?label={label.uuid}", [self.admin], results=[msg2])

        # a label belonging to another org isn't visible
        other_label = self.create_label("Other", org=self.org2)
        self.assertGet(endpoint_url + f"?label={other_label.uuid}", [self.admin], results=[])

        # an unknown label uuid returns nothing
        self.assertGet(endpoint_url + f"?label={contact1.uuid}", [self.admin], results=[])

        # can search by message text or contact name
        response = self.assertGet(endpoint_url + "?search=hello", [self.admin], results=[msg1])
        # searched responses also carry a total `count` of matches so the list UI can show "N results"
        self.assertEqual(1, response.json()["count"])
        response = self.assertGet(endpoint_url + "?search=bob", [self.admin], results=[msg2])
        self.assertEqual(1, response.json()["count"])

        # unfiltered listings still omit count — cursor pagination skips COUNT(*) when there is no search
        # ordering is `-created_on, -id`: old_msg is backdated 30 days so it sorts last
        response = self.assertGet(endpoint_url, [self.admin], results=[anon_msg, live_msg, msg2, msg1, old_msg])
        self.assertNotIn("count", response.json())

        # honor `?page_size=` so the list UI can request a page sized to its viewport
        msg3 = self.create_incoming_msg(contact1, "Three")
        msg4 = self.create_incoming_msg(contact1, "Four")
        response = self.assertGet(endpoint_url + "?page_size=2", [self.admin], results=[msg4, msg3])
        self.assertEqual(2, len(response.json()["results"]))
        # there should be a `next` cursor since we capped at 2 of 4
        self.assertIsNotNone(response.json()["next"])

    def test_notifications(self):
        endpoint_url = reverse("api.internal.notifications") + ".json"

        self.assertPostNotAllowed(endpoint_url)

        # simulate an export finishing
        export1 = ContactExport.create(self.org, self.admin)
        ExportFinishedNotificationType.create(export1)

        # simulate an export by another user finishing
        export2 = TicketExport.create(self.org, self.editor, start_date=timezone.now(), end_date=timezone.now())
        ExportFinishedNotificationType.create(export2)

        # and org being suspended
        self.org.suspend()

        export1_notification = export1.notifications.get()
        export2_notification = export2.notifications.get()
        suspended_notification = self.admin.notifications.get(notification_type="incident:started")

        self.assertGet(
            endpoint_url,
            [self.admin],
            results=[
                {
                    "type": "incident:started",
                    "created_on": matchers.ISODatetime(),
                    "url": f"/notification/read/{suspended_notification.id}/",
                    "is_seen": False,
                    "incident": {
                        "type": "org:suspended",
                        "started_on": matchers.ISODatetime(),
                        "ended_on": None,
                    },
                },
                {
                    "type": "export:finished",
                    "created_on": matchers.ISODatetime(),
                    "url": f"/notification/read/{export1_notification.id}/",
                    "is_seen": False,
                    "export": {"type": "contact", "num_records": None},
                },
            ],
        )

        # notifications are user specific
        self.assertGet(
            endpoint_url,
            [self.editor],
            results=[
                {
                    "type": "export:finished",
                    "created_on": matchers.ISODatetime(),
                    "url": f"/notification/read/{export2_notification.id}/",
                    "is_seen": False,
                    "export": {"type": "ticket", "num_records": None},
                },
            ],
        )

        # a DELETE marks all notifications as seen
        self.assertDelete(endpoint_url, self.admin)

        self.assertEqual(0, self.admin.notifications.filter(is_seen=False).count())
        self.assertEqual(2, self.admin.notifications.filter(is_seen=True).count())
        self.assertEqual(1, self.editor.notifications.filter(is_seen=False).count())

    def test_orgs(self):
        endpoint_url = reverse("api.internal.orgs") + ".json"
        self.assertGet(
            endpoint_url,
            [self.agent, self.editor, self.admin],
            results=[{"id": self.org.id, "name": "Nyaruka"}],
            num_queries=NUM_BASE_QUERIES + 1,
        )

    def test_shortcuts(self):
        endpoint_url = reverse("api.internal.shortcuts") + ".json"

        self.assertGetNotPermitted(endpoint_url, [None])
        self.assertPostNotAllowed(endpoint_url)
        self.assertDeleteNotAllowed(endpoint_url)

        shortcut1 = Shortcut.create(self.org, self.admin, "Planes", "Planes are...")
        shortcut2 = Shortcut.create(self.org, self.admin, "Trains", "Trains are...")
        deleted = Shortcut.create(self.org, self.admin, "Deleted", "Deleted shortcut")
        deleted.release(self.admin)
        Shortcut.create(self.org2, self.admin, "Cars", "Other org")

        self.assertGet(
            endpoint_url,
            [self.admin],
            results=[
                {
                    "uuid": str(shortcut2.uuid),
                    "name": "Trains",
                    "text": "Trains are...",
                    "modified_on": matchers.ISODatetime(),
                },
                {
                    "uuid": str(shortcut1.uuid),
                    "name": "Planes",
                    "text": "Planes are...",
                    "modified_on": matchers.ISODatetime(),
                },
            ],
            num_queries=NUM_BASE_QUERIES + 1,
        )

    def test_templates(self):
        endpoint_url = reverse("api.internal.templates") + ".json"

        self.assertGetNotPermitted(endpoint_url, [None, self.agent])
        self.assertPostNotAllowed(endpoint_url)
        self.assertDeleteNotAllowed(endpoint_url)

        tpl1 = self.create_template(
            "hello",
            [
                TemplateTranslation(
                    channel=self.channel,
                    locale="eng-US",
                    status=TemplateTranslation.STATUS_APPROVED,
                    external_id="1234",
                    external_locale="en_US",
                    namespace="foo_namespace",
                    components=[
                        {
                            "name": "body",
                            "type": "body/text",
                            "content": "Hi {{1}}",
                            "variables": {"1": 0},
                        }
                    ],
                    variables=[{"type": "text"}],
                ),
                TemplateTranslation(
                    channel=self.channel,
                    locale="fra-FR",
                    status=TemplateTranslation.STATUS_PENDING,
                    external_id="5678",
                    external_locale="fr_FR",
                    namespace="foo_namespace",
                    components=[
                        {
                            "name": "body",
                            "type": "body/text",
                            "content": "Bonjour {{1}}",
                            "variables": {"1": 0},
                        }
                    ],
                    variables=[{"type": "text"}],
                ),
            ],
        )
        tpl2 = self.create_template(
            "goodbye",
            [
                TemplateTranslation(
                    channel=self.channel,
                    locale="eng-US",
                    status=TemplateTranslation.STATUS_PENDING,
                    external_id="6789",
                    external_locale="en_US",
                    namespace="foo_namespace",
                    components=[
                        {
                            "name": "body",
                            "type": "body/text",
                            "content": "Goodbye {{1}}",
                            "variables": {"1": 0},
                        }
                    ],
                    variables=[{"type": "text"}],
                )
            ],
        )

        # template on other org to test filtering
        org2channel = self.create_channel("A", "Org2Channel", "123456", country="RW", org=self.org2)
        self.create_template(
            "goodbye",
            [
                TemplateTranslation(
                    channel=org2channel,
                    locale="eng-US",
                    status=TemplateTranslation.STATUS_PENDING,
                    external_id="6789",
                    external_locale="en_US",
                    namespace="foo_namespace",
                    components=[
                        {
                            "name": "body",
                            "type": "body/text",
                            "content": "Goodbye {{1}}",
                            "variables": {"1": 0},
                        }
                    ],
                    variables=[{"type": "text"}],
                )
            ],
            org=self.org2,
        )

        # no filtering
        self.assertGet(
            endpoint_url,
            [self.editor, self.admin],
            results=[
                {
                    "uuid": str(tpl2.uuid),
                    "name": "goodbye",
                    "base_translation": {
                        "channel": {"name": self.channel.name, "uuid": self.channel.uuid},
                        "locale": "eng-US",
                        "namespace": "foo_namespace",
                        "status": "pending",
                        "components": [
                            {
                                "name": "body",
                                "type": "body/text",
                                "content": "Goodbye {{1}}",
                                "variables": {"1": 0},
                            }
                        ],
                        "variables": [{"type": "text"}],
                        "supported": True,
                        "compatible": True,
                    },
                    "created_on": matchers.ISODatetime(),
                    "modified_on": matchers.ISODatetime(),
                },
                {
                    "uuid": str(tpl1.uuid),
                    "name": "hello",
                    "base_translation": {
                        "channel": {"name": self.channel.name, "uuid": self.channel.uuid},
                        "locale": "eng-US",
                        "namespace": "foo_namespace",
                        "status": "approved",
                        "components": [
                            {
                                "name": "body",
                                "type": "body/text",
                                "content": "Hi {{1}}",
                                "variables": {"1": 0},
                            }
                        ],
                        "variables": [{"type": "text"}],
                        "supported": True,
                        "compatible": True,
                    },
                    "created_on": matchers.ISODatetime(),
                    "modified_on": matchers.ISODatetime(),
                },
            ],
            num_queries=NUM_BASE_QUERIES + 3,
        )

    def test_llms(self):
        endpoint_url = reverse("api.internal.llms") + ".json"

        openai = LLM.create(self.org, self.admin, OpenAIType(), "gpt-4o", "GPT-4", {}, roles=LLM.ROLE_EDITING)
        anthropic = LLM.create(self.org, self.admin, AnthropicType(), "claude-3-5-haiku-20241022", "Claude", {})
        deleted = LLM.create(self.org, self.admin, AnthropicType(), "claude-3-5-haiku-20241022", "Deleted", {})
        deleted.release(self.admin)
        system = LLM.create(self.org, self.admin, OpenAIType(), "gpt-4o", "System", {})
        system.is_system = True
        system.save(update_fields=("is_system",))

        self.assertGetNotPermitted(endpoint_url, [None])
        self.assertPostNotAllowed(endpoint_url)
        self.assertDeleteNotAllowed(endpoint_url)

        self.assertGet(
            endpoint_url,
            [self.admin],
            results=[
                {
                    "uuid": str(anthropic.uuid),
                    "name": "Claude",
                    "type": "anthropic",
                    "roles": ["editing", "engine"],
                },
                {
                    "uuid": str(openai.uuid),
                    "name": "GPT-4",
                    "type": "openai",
                    "roles": ["editing"],
                },
                {
                    "uuid": str(system.uuid),
                    "name": "System",
                    "type": "openai",
                    "roles": ["editing", "engine"],
                },
            ],
        )

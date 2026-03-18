from django.urls import reverse
from django.utils import timezone

from temba.ai.models import LLM
from temba.ai.types.anthropic.type import AnthropicType
from temba.ai.types.openai.type import OpenAIType
from temba.api.tests.mixins import APITestMixin
from temba.contacts.models import ContactExport
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

        openai = LLM.create(self.org, self.admin, OpenAIType(), "gpt-4o", "GPT-4", {})
        anthropic = LLM.create(self.org, self.admin, AnthropicType(), "claude-3-5-haiku-20241022", "Claude", {})
        deleted = LLM.create(self.org, self.admin, AnthropicType(), "claude-3-5-haiku-20241022", "Deleted", {})
        deleted.release(self.admin)

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
                },
                {
                    "uuid": str(openai.uuid),
                    "name": "GPT-4",
                    "type": "openai",
                },
            ],
        )

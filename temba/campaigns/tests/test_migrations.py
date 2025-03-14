from temba.campaigns.models import Campaign, CampaignEvent
from temba.contacts.models import ContactField
from temba.tests import MigrationTest


class RemoveSingleMessageFlowsTest(MigrationTest):
    app = "campaigns"
    migrate_from = "0077_alter_campaignevent_flow"
    migrate_to = "0078_remove_single_message_flows"

    def setUpBeforeMigration(self, apps):
        group = self.create_group("Group", [])
        campaign = Campaign.create(self.org, self.admin, "Reminders", group)
        field = self.create_field("joined", "Joined", value_type=ContactField.TYPE_DATETIME)
        flow = self.create_flow("Test Flow")

        self.event1 = CampaignEvent.create_flow_event(
            self.org, self.admin, campaign, field, offset=30, unit="M", flow=flow, delivery_hour=13
        )
        self.event2 = CampaignEvent.create_message_event(
            self.org,
            self.admin,
            campaign,
            field,
            offset=12,
            unit="H",
            message={"eng": "Hello", "spa": "Hola"},
            base_language="eng",
            delivery_hour=9,
        )
        self.event3 = CampaignEvent.create_message_event(
            self.org,
            self.admin,
            campaign,
            field,
            offset=12,
            unit="H",
            message={"eng": "Hello", "spa": "Hola"},
            base_language="eng",
            delivery_hour=9,
        )

        self.single_message = self.create_flow("Single Message", is_system=True)
        self.event3.flow = self.single_message
        self.event3.save()

    def test_migration(self):
        # flow for flow event should be unaffected
        self.event1.refresh_from_db()
        self.event1.flow.refresh_from_db()
        self.assertIsNotNone(self.event1.flow)
        self.assertTrue(self.event1.flow.is_active)

        # message event without flow should be unaffected
        self.event2.refresh_from_db()
        self.assertIsNone(self.event2.flow)

        # message event with legacy single message flow should have flow released
        self.event3.refresh_from_db()
        self.single_message.refresh_from_db()
        self.assertIsNone(self.event3.flow)
        self.assertFalse(self.single_message.is_active)

from temba.campaigns.models import Campaign, CampaignEvent
from temba.contacts.models import ContactField
from temba.tests import MigrationTest


class BackfillCampaignEventTranslationsTest(MigrationTest):
    app = "campaigns"
    migrate_from = "0072_campaignevent_translations"
    migrate_to = "0073_backfill_campaignevent_translations"

    def setUpBeforeMigration(self, apps):
        group = self.create_group("Group", [])
        campaign = Campaign.create(self.org, self.admin, Campaign.get_unique_name(self.org, "Reminders"), group)
        field = self.create_field("joined", "Joined", value_type=ContactField.TYPE_DATETIME)
        flow = self.create_flow("Test Flow")

        self.event1 = CampaignEvent.create_flow_event(  # flow event
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
        )
        self.event3 = CampaignEvent.create_message_event(
            self.org,
            self.admin,
            campaign,
            field,
            offset=2,
            unit="W",
            message={"eng": "Goodbye", "spa": "Adios"},
            base_language="eng",
        )
        self.event3.translations = None
        self.event3.base_language = None
        self.event3.save(update_fields=("translations", "base_language"))

    def test_migration(self):
        def assert_translations(event, expected_translations, expected_base_language):
            event.refresh_from_db()
            self.assertEqual(event.translations, expected_translations)
            self.assertEqual(event.base_language, expected_base_language)

        assert_translations(self.event1, None, None)  # flow event should not have translations
        assert_translations(self.event2, {"eng": {"text": "Hello"}, "spa": {"text": "Hola"}}, "eng")
        assert_translations(self.event3, {"eng": {"text": "Goodbye"}, "spa": {"text": "Adios"}}, "eng")

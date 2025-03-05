from django.utils import timezone

from temba.campaigns.models import Campaign, CampaignEvent
from temba.contacts.models import ContactField, ContactFire
from temba.orgs.models import ItemCount
from temba.tests import MigrationTest


class BackfillFireCountsTest(MigrationTest):
    app = "campaigns"
    migrate_from = "0070_track_fire_counts"
    migrate_to = "0071_backfill_fire_counts"

    def setUpBeforeMigration(self, apps):
        contact1 = self.create_contact("Ann", phone="+1234567890")
        contact2 = self.create_contact("Bob", phone="+1234567891")
        contact3 = self.create_contact("Cat", phone="+1234567892")
        group = self.create_group("Group", [])
        campaign = Campaign.create(self.org, self.admin, "Reminders", group)
        joined = self.create_field("joined", "Joined", value_type=ContactField.TYPE_DATETIME)
        self.event1 = CampaignEvent.create_message_event(
            self.org, self.admin, campaign, joined, offset=1, unit="W", message="1", delivery_hour=13
        )
        self.event2 = CampaignEvent.create_message_event(
            self.org, self.admin, campaign, joined, offset=3, unit="D", message="2", delivery_hour=9
        )

        self.event1.fire_version = 1
        self.event1.save(update_fields=("fire_version",))

        self.event2.fire_version = 7
        self.event2.save(update_fields=("fire_version",))

        def create_fire(contact, event, fire_version=None):
            return ContactFire.objects.create(
                org=self.org,
                contact=contact,
                fire_type="C",
                scope=f"{event.id}:{fire_version or event.fire_version}",
                fire_on=timezone.now(),
            )

        create_fire(contact1, self.event1)
        create_fire(contact2, self.event1)
        create_fire(contact3, self.event1)
        create_fire(contact1, self.event2)
        create_fire(contact1, self.event2, fire_version=6)  # not the current version
        create_fire(contact2, self.event2)
        ContactFire.objects.create(org=self.org, contact=contact1, fire_type="S", scope="", fire_on=timezone.now())

        # unrelated item count to check that it's not deleted
        ItemCount.objects.create(org=self.org, scope="foo:1", count=123, is_squashed=True)

    def test_migration(self):
        actual = {
            c["scope"]: c["count"]
            for c in self.org.counts.filter(scope__startswith="campfires:").values("scope", "count")
        }
        self.assertEqual({f"campfires:{self.event1.id}:1": 3, f"campfires:{self.event2.id}:7": 2}, actual)

        self.assertTrue(ItemCount.objects.filter(org=self.org, scope="foo:1", count=123, is_squashed=True).exists())

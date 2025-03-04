from django.utils import timezone

from temba.contacts.models import ContactFire
from temba.tests import MigrationTest


class AddVersionToEventFiresTest(MigrationTest):
    app = "campaigns"
    migrate_from = "0067_campaignevent_status"
    migrate_to = "0068_add_version_to_event_fires"

    def setUpBeforeMigration(self, apps):
        contact = self.create_contact("Bob", phone="+1234567890")

        self.fire1 = ContactFire.objects.create(
            org=self.org, contact=contact, fire_type="C", scope="1234", fire_on=timezone.now()
        )
        self.fire2 = ContactFire.objects.create(
            org=self.org, contact=contact, fire_type="C", scope="2345", fire_on=timezone.now()
        )
        self.fire3 = ContactFire.objects.create(
            org=self.org, contact=contact, fire_type="C", scope="3456:1", fire_on=timezone.now()
        )

    def test_migration(self):
        self.fire1.refresh_from_db()
        self.fire2.refresh_from_db()
        self.fire3.refresh_from_db()

        self.assertEqual(self.fire1.scope, "1234:1")
        self.assertEqual(self.fire2.scope, "2345:1")
        self.assertEqual(self.fire3.scope, "3456:1")

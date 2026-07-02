from datetime import datetime, timedelta, timezone as tzone

from temba.channels.models import ChannelEvent
from temba.contacts.models import ContactURN
from temba.tests import MigrationTest


class FixBadLastSeenOnsTest(MigrationTest):
    app = "contacts"
    migrate_from = "0214_alter_contactimport_uuid"
    migrate_to = "0215_fix_bad_last_seen_ons"

    def setUpBeforeMigration(self, apps):
        zero_date = datetime(1, 1, 1, 0, 0, tzinfo=tzone.utc)
        good_date = datetime(2025, 6, 15, 12, 0, tzinfo=tzone.utc)

        # contact with bad last_seen_on and a message
        self.contact1 = self.create_contact("Bob", urns=["tel:+593979000001"])
        self.msg1 = self.create_incoming_msg(self.contact1, "Hello")
        self.contact1.last_seen_on = zero_date
        self.contact1.save(update_fields=["last_seen_on"])

        # contact with bad last_seen_on and no messages/events
        self.contact2 = self.create_contact("Jim", urns=["tel:+593979000002"])
        self.contact2.last_seen_on = zero_date
        self.contact2.save(update_fields=["last_seen_on"])

        # contact with good last_seen_on - should not be affected
        self.contact3 = self.create_contact("Ann", urns=["tel:+593979000003"])
        self.contact3.last_seen_on = good_date
        self.contact3.save(update_fields=["last_seen_on"])

        # contact with bad last_seen_on, message and event - should pick newest
        self.contact4 = self.create_contact("Eve", urns=["tel:+593979000004"])
        self.msg4 = self.create_incoming_msg(self.contact4, "Hi")
        self.evt4 = self.create_channel_event(
            self.channel,
            "tel:+593979000004",
            ChannelEvent.TYPE_CALL_IN_MISSED,
        )
        # set event's created_on to be later than message's created_on
        self.evt4.created_on = self.msg4.created_on + timedelta(hours=1)
        self.evt4.save(update_fields=["created_on"])
        self.contact4.last_seen_on = zero_date
        self.contact4.save(update_fields=["last_seen_on"])

        self.start = datetime.now(tzone.utc)

    def test_migration(self):
        self.contact1.refresh_from_db()
        self.assertEqual(self.msg1.created_on, self.contact1.last_seen_on)
        self.assertGreater(self.contact1.modified_on, self.start)

        # contact with no messages/events falls back to modified_on
        self.contact2.refresh_from_db()
        self.assertIsNotNone(self.contact2.last_seen_on)
        self.assertGreater(self.contact2.modified_on, self.start)

        self.contact3.refresh_from_db()
        self.assertEqual(datetime(2025, 6, 15, 12, 0, tzinfo=tzone.utc), self.contact3.last_seen_on)
        self.assertLess(self.contact3.modified_on, self.start)

        self.contact4.refresh_from_db()
        self.assertEqual(self.evt4.created_on, self.contact4.last_seen_on)  # event is newer than message
        self.assertGreater(self.contact4.modified_on, self.start)


class FlipWhatsAppTelURNsTest(MigrationTest):
    app = "contacts"
    migrate_from = "0216_remove_contact_contacts_contact_org_modified_and_more"
    migrate_to = "0217_flip_whatsapp_tel_urns"

    def setUpBeforeMigration(self, apps):
        # a contact reachable only by a whatsapp URN -> becomes tel
        self.contact1 = self.create_contact("Ann", urns=["whatsapp:250788000001"])

        # a contact reachable only by a bsuid URN -> becomes whatsapp
        self.contact2 = self.create_contact("Bob", urns=["bsuid:RW.abc123"])

        # a typical WhatsApp Cloud contact with both whatsapp (phone) and bsuid (user id) URNs
        self.contact3 = self.create_contact("Cat", urns=["whatsapp:250788000003", "bsuid:RW.def456"])

        # a contact that already has the tel URN that its whatsapp URN would flip to -> whatsapp is left as-is
        self.contact4 = self.create_contact("Dan", urns=["tel:+250788000004", "whatsapp:250788000004"])

        # a contact with unrelated schemes that should never be touched
        self.contact5 = self.create_contact("Eve", urns=["tel:+250788000005", "facebook:123456789"])

        self.start = datetime.now(tzone.utc)

    def urns(self, contact) -> set:
        return {(u.scheme, u.path, u.identity) for u in contact.urns.all()}

    def test_migration(self):
        # whatsapp URN flipped to tel with a leading + added to the path
        self.contact1.refresh_from_db()
        self.assertEqual({("tel", "+250788000001", "tel:+250788000001")}, self.urns(self.contact1))
        self.assertGreater(self.contact1.modified_on, self.start)

        # bsuid URN flipped to whatsapp with the path unchanged
        self.contact2.refresh_from_db()
        self.assertEqual({("whatsapp", "RW.abc123", "whatsapp:RW.abc123")}, self.urns(self.contact2))
        self.assertGreater(self.contact2.modified_on, self.start)

        # both URNs flipped
        self.contact3.refresh_from_db()
        self.assertEqual(
            {
                ("tel", "+250788000003", "tel:+250788000003"),
                ("whatsapp", "RW.def456", "whatsapp:RW.def456"),
            },
            self.urns(self.contact3),
        )
        self.assertGreater(self.contact3.modified_on, self.start)

        # colliding whatsapp URN left untouched (can't flip without violating uniqueness), so not reindexed
        self.contact4.refresh_from_db()
        self.assertEqual(
            {
                ("tel", "+250788000004", "tel:+250788000004"),
                ("whatsapp", "250788000004", "whatsapp:250788000004"),
            },
            self.urns(self.contact4),
        )
        self.assertLess(self.contact4.modified_on, self.start)

        # unrelated URNs untouched and contact not reindexed
        self.contact5.refresh_from_db()
        self.assertEqual(
            {
                ("tel", "+250788000005", "tel:+250788000005"),
                ("facebook", "123456789", "facebook:123456789"),
            },
            self.urns(self.contact5),
        )
        self.assertLess(self.contact5.modified_on, self.start)

        # no whatsapp-scheme phone URNs or bsuid URNs remain (other than the skipped collision)
        self.assertEqual(0, ContactURN.objects.filter(scheme="bsuid").count())
        self.assertEqual(1, ContactURN.objects.filter(scheme="whatsapp", path="250788000004").count())

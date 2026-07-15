from datetime import datetime, timezone as tzone
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from temba.contacts.models import ContactURN
from temba.tests import TembaTest


class BsuidToWhatsAppTest(TembaTest):
    def urns(self, contact) -> set:
        contact.refresh_from_db()
        return {(u.scheme, u.path, u.identity) for u in contact.urns.all()}

    def test_command(self):
        # a contact reachable only by a bsuid URN -> becomes whatsapp with the same path
        contact1 = self.create_contact("Ann", urns=["bsuid:RW.abc123"])

        # a whatsapp Cloud contact with both a whatsapp phone URN and a bsuid URN -> only the bsuid flips,
        # the whatsapp phone URN is left as-is (never changed to tel)
        contact2 = self.create_contact("Bob", urns=["whatsapp:250788000002", "bsuid:RW.def456"])

        # a contact with a tel and a bsuid -> tel untouched, bsuid flips
        contact3 = self.create_contact("Cat", urns=["tel:+250788000003", "bsuid:RW.ghi789"])

        # a contact with no bsuid -> never touched
        contact4 = self.create_contact("Dan", urns=["whatsapp:250788000004", "tel:+250788000004"])

        # a bsuid whose whatsapp target already exists on a *different* contact -> left as-is (collision)
        contact5 = self.create_contact("Eve", urns=["bsuid:RW.jkl012"])
        contact6 = self.create_contact("Fay", urns=["whatsapp:RW.jkl012"])

        start = datetime.now(tzone.utc)

        out = StringIO()
        call_command("bsuid_to_whatsapp", stdout=out)

        # bsuid flipped to whatsapp, path unchanged, contact reindexed
        self.assertEqual({("whatsapp", "RW.abc123", "whatsapp:RW.abc123")}, self.urns(contact1))
        self.assertGreater(contact1.modified_on, start)

        # bsuid flipped; whatsapp phone URN untouched (NOT changed to tel)
        self.assertEqual(
            {("whatsapp", "250788000002", "whatsapp:250788000002"), ("whatsapp", "RW.def456", "whatsapp:RW.def456")},
            self.urns(contact2),
        )
        self.assertGreater(contact2.modified_on, start)

        # tel untouched, bsuid flipped
        self.assertEqual(
            {("tel", "+250788000003", "tel:+250788000003"), ("whatsapp", "RW.ghi789", "whatsapp:RW.ghi789")},
            self.urns(contact3),
        )
        self.assertGreater(contact3.modified_on, start)

        # no bsuid -> nothing touched, not reindexed
        self.assertEqual(
            {("whatsapp", "250788000004", "whatsapp:250788000004"), ("tel", "+250788000004", "tel:+250788000004")},
            self.urns(contact4),
        )
        self.assertLess(contact4.modified_on, start)

        # colliding bsuid (whatsapp target owned by another contact) left as-is, not reindexed
        self.assertEqual({("bsuid", "RW.jkl012", "bsuid:RW.jkl012")}, self.urns(contact5))
        self.assertLess(contact5.modified_on, start)
        self.assertEqual({("whatsapp", "RW.jkl012", "whatsapp:RW.jkl012")}, self.urns(contact6))
        self.assertLess(contact6.modified_on, start)

        self.assertIn("Migrated 3 bsuid URNs to whatsapp (0 redundant dropped)", out.getvalue())

        # only the collided bsuid remains
        self.assertEqual({"RW.jkl012"}, set(ContactURN.objects.filter(scheme="bsuid").values_list("path", flat=True)))

    def test_reapplying_is_safe(self):
        contact = self.create_contact("Bob", urns=["whatsapp:250788000002", "bsuid:RW.def456"])

        call_command("bsuid_to_whatsapp", stdout=StringIO())
        before = self.urns(contact)
        contact.refresh_from_db()
        modified_before = contact.modified_on

        # running again changes nothing and doesn't reindex
        out = StringIO()
        call_command("bsuid_to_whatsapp", stdout=out)

        self.assertEqual(before, self.urns(contact))
        contact.refresh_from_db()
        self.assertEqual(modified_before, contact.modified_on)
        self.assertIn("Migrated 0 bsuid URNs to whatsapp (0 redundant dropped)", out.getvalue())

    def test_redundant_bsuid_dropped_and_content_moved(self):
        # a contact that already has the equivalent whatsapp URN plus a duplicate bsuid (e.g. an updated
        # channel wrote the whatsapp form while the old bsuid still lingers); the tel URN just lets us create
        # an incoming message via the default channel before pointing it at the bsuid URN
        contact = self.create_contact("Cat", urns=["tel:+250788000009", "whatsapp:RW.def456", "bsuid:RW.def456"])
        wa = contact.urns.get(scheme="whatsapp")
        bsuid = contact.urns.get(scheme="bsuid")

        # a message referencing the bsuid URN that will be dropped (PROTECT would block a bare delete)
        msg = self.create_incoming_msg(contact, "hi")
        msg.contact_urn = bsuid
        msg.save(update_fields=["contact_urn"])

        start = datetime.now(tzone.utc)

        out = StringIO()
        call_command("bsuid_to_whatsapp", stdout=out)

        # the redundant bsuid is gone and its message was moved onto the surviving whatsapp URN
        self.assertFalse(ContactURN.objects.filter(id=bsuid.id).exists())
        self.assertEqual(
            {("tel", "+250788000009", "tel:+250788000009"), ("whatsapp", "RW.def456", "whatsapp:RW.def456")},
            self.urns(contact),
        )
        msg.refresh_from_db()
        self.assertEqual(wa.id, msg.contact_urn_id)

        # the drop path also reindexes the contact
        self.assertGreater(contact.modified_on, start)
        self.assertIn("Migrated 0 bsuid URNs to whatsapp (1 redundant dropped)", out.getvalue())

    def test_lowercase_country_code_is_normalized(self):
        # a legacy bsuid whose country code is lowercase (created directly to bypass URN normalization); the
        # command must normalize the path so the flipped whatsapp URN is canonical and passes URN.validate
        contact = self.create_contact("Ann", urns=["tel:+250788000001"])
        ContactURN.objects.create(
            org=self.org, contact=contact, scheme="bsuid", path="rw.abc123", identity="bsuid:rw.abc123", priority=50
        )

        # a lowercase bsuid whose *normalized* whatsapp target already exists on another contact -> it must
        # still be detected as a collision (proving the lookup normalizes too) and left untouched
        collide = self.create_contact("Cat", urns=[])
        ContactURN.objects.create(
            org=self.org, contact=collide, scheme="bsuid", path="rw.zzz999", identity="bsuid:rw.zzz999", priority=50
        )
        self.create_contact("Bob", urns=["whatsapp:RW.zzz999"])

        call_command("bsuid_to_whatsapp", stdout=StringIO())

        # the lowercase bsuid flipped to a normalized (uppercase CC) whatsapp URN
        self.assertEqual(
            {("tel", "+250788000001", "tel:+250788000001"), ("whatsapp", "RW.abc123", "whatsapp:RW.abc123")},
            self.urns(contact),
        )

        # the lowercase bsuid colliding with another contact's normalized whatsapp URN was left as-is
        self.assertEqual({("bsuid", "rw.zzz999", "bsuid:rw.zzz999")}, self.urns(collide))

    @patch("temba.contacts.management.commands.bsuid_to_whatsapp.BATCH_SIZE", 2)
    def test_batches_and_skips_collisions_across_the_cursor(self):
        # an existing whatsapp URN that a later bsuid will collide with when it tries to flip
        self.create_contact("Taken", urns=["whatsapp:RW.taken0"])

        # several bsuid contacts spanning multiple batches of 2, plus one whose target already exists
        good = [self.create_contact(f"C{i}", urns=[f"bsuid:RW.user{i}"]) for i in range(5)]
        collide = self.create_contact("Collide", urns=["bsuid:RW.taken0"])

        # with BATCH_SIZE=2 the collided bsuid is skipped mid-cursor; if last_id didn't advance past it the
        # command would loop forever, so simply completing proves the cursor advances correctly
        call_command("bsuid_to_whatsapp", stdout=StringIO())

        # every non-colliding bsuid was flipped to whatsapp across all batches
        for i, contact in enumerate(good):
            self.assertEqual({("whatsapp", f"RW.user{i}", f"whatsapp:RW.user{i}")}, self.urns(contact))

        # the colliding bsuid is left untouched
        self.assertEqual({("bsuid", "RW.taken0", "bsuid:RW.taken0")}, self.urns(collide))

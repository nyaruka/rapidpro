from datetime import datetime, timezone as tzone
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from temba.contacts.models import ContactURN
from temba.tests import TembaTest


class FlipWhatsAppUrnsTest(TembaTest):
    def urns(self, contact) -> set:
        contact.refresh_from_db()
        return {(u.scheme, u.path, u.identity) for u in contact.urns.all()}

    def test_command(self):
        # a contact with a whatsapp URN but NO bsuid -> left untouched (only bsuid contacts are flipped)
        contact1 = self.create_contact("Ann", urns=["whatsapp:250788000001"])

        # a contact reachable only by a bsuid URN -> becomes whatsapp
        contact2 = self.create_contact("Bob", urns=["bsuid:RW.abc123"])

        # a typical WhatsApp Cloud contact with both whatsapp (phone) and bsuid (user id) URNs -> both flipped
        contact3 = self.create_contact("Cat", urns=["whatsapp:250788000003", "bsuid:RW.def456"])

        # a bsuid contact whose whatsapp phone duplicates its own tel -> whatsapp dropped, bsuid flipped
        contact4 = self.create_contact("Dan", urns=["tel:+250788000004", "whatsapp:250788000004", "bsuid:RW.jkl012"])

        # a contact with unrelated schemes and no bsuid -> never touched
        contact5 = self.create_contact("Eve", urns=["tel:+250788000005", "facebook:123456789"])

        # a bsuid contact whose whatsapp target already exists (contact7) -> bsuid left as-is (collision)
        contact6 = self.create_contact("Fay", urns=["bsuid:RW.ghi789"])
        contact7 = self.create_contact("Gus", urns=["whatsapp:RW.ghi789"])

        start = datetime.now(tzone.utc)

        out = StringIO()
        call_command("flip_whatsapp_urns", stdout=out)

        # no bsuid -> whatsapp phone URN is NOT flipped to tel, contact not reindexed
        self.assertEqual({("whatsapp", "250788000001", "whatsapp:250788000001")}, self.urns(contact1))
        self.assertLess(contact1.modified_on, start)

        # bsuid URN flipped to whatsapp with the path unchanged
        self.assertEqual({("whatsapp", "RW.abc123", "whatsapp:RW.abc123")}, self.urns(contact2))
        self.assertGreater(contact2.modified_on, start)

        # both URNs flipped
        self.assertEqual(
            {("tel", "+250788000003", "tel:+250788000003"), ("whatsapp", "RW.def456", "whatsapp:RW.def456")},
            self.urns(contact3),
        )
        self.assertGreater(contact3.modified_on, start)

        # redundant whatsapp phone (duplicates own tel) dropped, bsuid flipped to whatsapp
        self.assertEqual(
            {
                ("tel", "+250788000004", "tel:+250788000004"),
                ("whatsapp", "RW.jkl012", "whatsapp:RW.jkl012"),
            },
            self.urns(contact4),
        )
        self.assertGreater(contact4.modified_on, start)

        # unrelated URNs untouched and contact not reindexed
        self.assertEqual(
            {("tel", "+250788000005", "tel:+250788000005"), ("facebook", "123456789", "facebook:123456789")},
            self.urns(contact5),
        )
        self.assertLess(contact5.modified_on, start)

        # bsuid whose whatsapp target already exists is left as-is, so not reindexed
        self.assertEqual({("bsuid", "RW.ghi789", "bsuid:RW.ghi789")}, self.urns(contact6))
        self.assertLess(contact6.modified_on, start)

        # the injected whatsapp business-scoped URN is untouched (non-digit path)
        self.assertEqual({("whatsapp", "RW.ghi789", "whatsapp:RW.ghi789")}, self.urns(contact7))
        self.assertLess(contact7.modified_on, start)

        self.assertIn(
            "Flipped 1 whatsapp URNs to tel (1 redundant dropped) and 3 bsuid URNs to whatsapp across 4 contacts",
            out.getvalue(),
        )

        # only the collided bsuid remains
        self.assertEqual({"RW.ghi789"}, set(ContactURN.objects.filter(scheme="bsuid").values_list("path", flat=True)))

    def test_reapplying_is_safe(self):
        contact = self.create_contact("Cat", urns=["whatsapp:250788000003", "bsuid:RW.def456"])

        call_command("flip_whatsapp_urns", stdout=StringIO())
        before = self.urns(contact)
        contact.refresh_from_db()
        modified_before = contact.modified_on

        # running again changes nothing and doesn't reindex
        out = StringIO()
        call_command("flip_whatsapp_urns", stdout=out)

        self.assertEqual(before, self.urns(contact))
        contact.refresh_from_db()
        self.assertEqual(modified_before, contact.modified_on)
        self.assertIn(
            "Flipped 0 whatsapp URNs to tel (0 redundant dropped) and 0 bsuid URNs to whatsapp across 0 contacts",
            out.getvalue(),
        )

    def test_dropped_whatsapp_moves_references_to_tel(self):
        # a contact whose whatsapp phone duplicates its own tel, with a bsuid taking over the whatsapp slot
        contact = self.create_contact("Dan", urns=["tel:+250788000004", "whatsapp:250788000004", "bsuid:RW.jkl012"])
        wa = contact.urns.get(scheme="whatsapp", path="250788000004")
        tel = contact.urns.get(scheme="tel")

        # a message referencing the whatsapp URN that will be dropped (PROTECT would block a bare delete)
        msg = self.create_incoming_msg(contact, "hi")
        msg.contact_urn = wa
        msg.save(update_fields=["contact_urn"])

        call_command("flip_whatsapp_urns", stdout=StringIO())

        # the redundant whatsapp URN is gone and its message was moved onto the surviving tel URN
        self.assertFalse(ContactURN.objects.filter(id=wa.id).exists())
        msg.refresh_from_db()
        self.assertEqual(tel.id, msg.contact_urn_id)

    @patch("temba.contacts.management.commands.flip_whatsapp_urns.BATCH_SIZE", 2)
    def test_batches_and_skips_collisions_across_the_cursor(self):
        # an existing whatsapp URN that a later bsuid will collide with when it tries to flip
        self.create_contact("Taken", urns=["whatsapp:RW.taken0"])

        # several bsuid contacts spanning multiple batches of 2, plus one whose target already exists
        good = [self.create_contact(f"C{i}", urns=[f"bsuid:RW.user{i}"]) for i in range(5)]
        collide = self.create_contact("Collide", urns=["bsuid:RW.taken0"])

        # with BATCH_SIZE=2 the collided bsuid is skipped mid-cursor; if last_id didn't advance past it the
        # command would loop forever, so simply completing proves the cursor advances correctly
        call_command("flip_whatsapp_urns", stdout=StringIO())

        # every non-colliding bsuid was flipped to whatsapp across all batches
        for i, contact in enumerate(good):
            self.assertEqual({("whatsapp", f"RW.user{i}", f"whatsapp:RW.user{i}")}, self.urns(contact))

        # the colliding bsuid is left untouched
        self.assertEqual({("bsuid", "RW.taken0", "bsuid:RW.taken0")}, self.urns(collide))

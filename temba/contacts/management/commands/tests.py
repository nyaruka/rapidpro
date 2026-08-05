from datetime import datetime, timezone as tzone
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from temba.contacts.models import ContactURN
from temba.tests import TembaTest, mock_mailroom


class ConvertBsuidUrnsTest(TembaTest):
    def urns(self, contact) -> set:
        contact.refresh_from_db()
        return {(u.scheme, u.path, u.identity) for u in contact.urns.all()}

    @mock_mailroom
    def test_command(self, mr_mocks):
        # a contact with a whatsapp phone URN and no bsuid -> never touched
        contact1 = self.create_contact("Ann", urns=["whatsapp:250788000001"])

        # a contact reachable only by a bsuid URN -> converted to whatsapp
        contact2 = self.create_contact("Bob", urns=["bsuid:RW.abc123"])

        # a typical WhatsApp contact with a phone whatsapp URN above its bsuid URN -> bsuid converted, and its
        # priority (already below the phone's) left alone
        contact3 = self.create_contact("Cat", urns=["whatsapp:250788000003", "bsuid:RW.def456"])

        # a contact that courier has dual-written -> the bsuid URN is redundant and dropped
        contact4 = self.create_contact("Dan", urns=["whatsapp:250788000004", "whatsapp:RW.jkl012", "bsuid:RW.jkl012"])

        # a contact with unrelated schemes -> never touched
        contact5 = self.create_contact("Eve", urns=["tel:+250788000005", "facebook:123456789"])

        # a bsuid contact whose whatsapp identity belongs to a different contact -> left as-is
        contact6 = self.create_contact("Fay", urns=["bsuid:RW.ghi789"])
        contact7 = self.create_contact("Gus", urns=["whatsapp:RW.ghi789"])

        # a contact whose bsuid URN outranks its phone whatsapp URN -> converted but dropped below the phone
        contact8 = self.create_contact("Hal", urns=["bsuid:RW.mno345", "whatsapp:250788000008"])

        start = datetime.now(tzone.utc)

        out = StringIO()
        call_command("convert_bsuid_urns", stdout=out)

        # no bsuid -> not touched or reindexed
        self.assertEqual({("whatsapp", "250788000001", "whatsapp:250788000001")}, self.urns(contact1))
        self.assertLess(contact1.modified_on, start)

        # bsuid URN converted to whatsapp with the path unchanged
        self.assertEqual({("whatsapp", "RW.abc123", "whatsapp:RW.abc123")}, self.urns(contact2))
        self.assertGreater(contact2.modified_on, start)

        # bsuid URN converted, phone whatsapp URN untouched and still ranked above it
        self.assertEqual(
            {
                ("whatsapp", "250788000003", "whatsapp:250788000003"),
                ("whatsapp", "RW.def456", "whatsapp:RW.def456"),
            },
            self.urns(contact3),
        )
        self.assertEqual(1000, contact3.urns.get(path="250788000003").priority)
        self.assertEqual(999, contact3.urns.get(path="RW.def456").priority)
        self.assertGreater(contact3.modified_on, start)

        # redundant bsuid dropped, existing whatsapp URNs untouched
        self.assertEqual(
            {
                ("whatsapp", "250788000004", "whatsapp:250788000004"),
                ("whatsapp", "RW.jkl012", "whatsapp:RW.jkl012"),
            },
            self.urns(contact4),
        )
        self.assertGreater(contact4.modified_on, start)

        # unrelated URNs never touched
        self.assertEqual(
            {("tel", "+250788000005", "tel:+250788000005"), ("facebook", "123456789", "facebook:123456789")},
            self.urns(contact5),
        )
        self.assertLess(contact5.modified_on, start)

        # bsuid whose whatsapp identity belongs to another contact is left as-is
        self.assertEqual({("bsuid", "RW.ghi789", "bsuid:RW.ghi789")}, self.urns(contact6))
        self.assertLess(contact6.modified_on, start)
        self.assertEqual({("whatsapp", "RW.ghi789", "whatsapp:RW.ghi789")}, self.urns(contact7))
        self.assertLess(contact7.modified_on, start)

        # bsuid that outranked the phone (1000 vs 999) is converted with its priority dropped below the phone's
        self.assertEqual(
            {
                ("whatsapp", "RW.mno345", "whatsapp:RW.mno345"),
                ("whatsapp", "250788000008", "whatsapp:250788000008"),
            },
            self.urns(contact8),
        )
        self.assertEqual(999, contact8.urns.get(path="250788000008").priority)
        self.assertEqual(998, contact8.urns.get(path="RW.mno345").priority)
        self.assertGreater(contact8.modified_on, start)

        # every changed contact was sent to mailroom for re-indexing
        self.assertEqual(1, len(mr_mocks.calls["contact_reindex"]))
        org_arg, contacts_arg = mr_mocks.calls["contact_reindex"][0].args
        self.assertEqual(self.org, org_arg)
        self.assertEqual({contact2, contact3, contact4, contact8}, set(contacts_arg))

        self.assertIn(
            "Converted 3 bsuid URNs to whatsapp (1 redundant dropped, "
            "1 skipped as whatsapp URN belongs to a different contact) across 4 contacts",
            out.getvalue(),
        )

        # only the collided bsuid remains
        self.assertEqual({"RW.ghi789"}, set(ContactURN.objects.filter(scheme="bsuid").values_list("path", flat=True)))

    @mock_mailroom
    def test_dropped_bsuid_moves_references(self, mr_mocks):
        # a dual-written contact whose bsuid URN is redundant and referenced by a message
        contact = self.create_contact("Dan", urns=["whatsapp:250788000004", "whatsapp:RW.jkl012", "bsuid:RW.jkl012"])
        bsuid = contact.urns.get(scheme="bsuid")
        wa = contact.urns.get(scheme="whatsapp", path="RW.jkl012")

        # a message referencing the bsuid URN that will be dropped (PROTECT would block a bare delete)
        msg = self.create_incoming_msg(contact, "hi", channel=self.channel)
        msg.contact_urn = bsuid
        msg.save(update_fields=["contact_urn"])

        call_command("convert_bsuid_urns", stdout=StringIO())

        # the redundant bsuid URN is gone and its message was moved onto the surviving whatsapp URN
        self.assertFalse(ContactURN.objects.filter(id=bsuid.id).exists())
        msg.refresh_from_db()
        self.assertEqual(wa.id, msg.contact_urn_id)

    @mock_mailroom
    def test_reapplying_is_safe(self, mr_mocks):
        contact = self.create_contact("Cat", urns=["whatsapp:250788000003", "bsuid:RW.def456"])

        call_command("convert_bsuid_urns", stdout=StringIO())
        before = self.urns(contact)
        contact.refresh_from_db()
        modified_before = contact.modified_on
        reindexes_before = len(mr_mocks.calls["contact_reindex"])

        # running again changes nothing and doesn't reindex
        out = StringIO()
        call_command("convert_bsuid_urns", stdout=out)

        self.assertEqual(before, self.urns(contact))
        contact.refresh_from_db()
        self.assertEqual(modified_before, contact.modified_on)
        self.assertEqual(reindexes_before, len(mr_mocks.calls["contact_reindex"]))
        self.assertIn(
            "Converted 0 bsuid URNs to whatsapp (0 redundant dropped, "
            "0 skipped as whatsapp URN belongs to a different contact) across 0 contacts",
            out.getvalue(),
        )

    @mock_mailroom
    @patch("temba.contacts.management.commands.convert_bsuid_urns.BATCH_SIZE", 2)
    def test_batches_and_skips_collisions_across_the_cursor(self, mr_mocks):
        # an existing whatsapp URN that a later bsuid will collide with when it tries to convert
        self.create_contact("Taken", urns=["whatsapp:RW.taken0"])

        # several bsuid contacts spanning multiple batches of 2, plus one whose target already exists
        good = [self.create_contact(f"C{i}", urns=[f"bsuid:RW.user{i}"]) for i in range(5)]
        collide = self.create_contact("Collide", urns=["bsuid:RW.taken0"])

        # with BATCH_SIZE=2 the collided bsuid is skipped mid-cursor; if last_id didn't advance past it the
        # command would loop forever, so simply completing proves the cursor advances correctly
        call_command("convert_bsuid_urns", stdout=StringIO())

        # every non-colliding bsuid was converted to whatsapp across all batches
        for i, contact in enumerate(good):
            self.assertEqual({("whatsapp", f"RW.user{i}", f"whatsapp:RW.user{i}")}, self.urns(contact))

        # the colliding bsuid is left untouched
        self.assertEqual({("bsuid", "RW.taken0", "bsuid:RW.taken0")}, self.urns(collide))

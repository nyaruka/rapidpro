from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.db.models.functions import Now

from temba.contacts.models import URN, Contact, ContactURN

BATCH_SIZE = 1000


class Command(BaseCommand):
    help = (
        "Flips WhatsApp contact URNs to the new scheme model, only for contacts that have a BSUID URN: "
        "whatsapp:<e164 digits> -> tel:+<e164 digits> (the phone identity) and "
        "bsuid:<CC.alphanumeric> -> whatsapp:<CC.alphanumeric> (the business-scoped user id). "
        "A whatsapp phone URN that duplicates a tel URN already on the same contact is dropped instead."
    )

    def handle(self, *args, **options):
        num_contacts = num_wa = num_dropped = num_bsuid = 0
        last_id = 0

        while True:
            # process one batch of contacts that have a bsuid URN, cursoring by bsuid URN id so that skipped
            # (collision) rows and already-flipped rows aren't re-fetched forever
            bsuid_urns = list(
                ContactURN.objects.filter(scheme="bsuid", id__gt=last_id)
                .order_by("id")
                .only("id", "org_id", "path", "contact_id")[:BATCH_SIZE]
            )
            if not bsuid_urns:
                break

            last_id = bsuid_urns[-1].id
            contact_ids = {u.contact_id for u in bsuid_urns if u.contact_id}

            # the phone (all-digit) whatsapp URNs of those same contacts, which become tel URNs; restricting to
            # digit paths leaves already-flipped whatsapp business-scoped ids alone so this is safe to re-run
            wa_urns = list(
                ContactURN.objects.filter(scheme="whatsapp", contact_id__in=contact_ids, path__regex=r"^[0-9]+$").only(
                    "id", "org_id", "path", "contact_id"
                )
            )

            n_wa, dropped, contacts_wa = self._flip(wa_urns, to_scheme="tel", add_plus=True, drop_owner_collisions=True)
            n_bsuid, _, contacts_bsuid = self._flip(bsuid_urns, to_scheme="whatsapp", add_plus=False)

            # bump modified_on on flipped contacts so the search indexer picks up the change
            reindex = contacts_wa | contacts_bsuid
            if reindex:
                Contact.objects.filter(id__in=reindex).update(modified_on=Now())

            num_wa += n_wa
            num_dropped += dropped
            num_bsuid += n_bsuid
            num_contacts += len(contact_ids)

        self.stdout.write(
            f"Flipped {num_wa} whatsapp URNs to tel ({num_dropped} redundant dropped) and "
            f"{num_bsuid} bsuid URNs to whatsapp across {num_contacts} contacts with a BSUID"
        )

    def _flip(self, urns, *, to_scheme, add_plus, drop_owner_collisions=False):
        """
        Flips the given URNs to to_scheme. A URN whose target identity already exists for the org is a
        collision and is normally left untouched (it can't be flipped without violating the (identity, org)
        uniqueness constraint). When drop_owner_collisions is set and the colliding identity is already held
        by the *same* contact, the source URN is redundant, so its message/call/event references are moved
        onto the existing URN and the source is deleted - used for the whatsapp -> tel flip, where such a
        whatsapp URN just duplicates the contact's phone URN and the BSUID is taking over the whatsapp slot.

        Returns (num_flipped, num_dropped, {contact_ids}).
        """
        if not urns:
            return 0, 0, set()

        def target_path(u):
            return ("+" + u.path) if add_plus else u.path

        # existing (org_id, identity) -> (owning contact_id, URN id), to detect collisions and, for owner
        # collisions, find the surviving URN to move references onto
        existing = {
            (org_id, identity): (contact_id, urn_id)
            for org_id, identity, contact_id, urn_id in ContactURN.objects.filter(
                org_id__in={u.org_id for u in urns},
                identity__in={URN.from_parts(to_scheme, target_path(u)) for u in urns},
            ).values_list("org_id", "identity", "contact_id", "id")
        }

        to_update, contact_ids, num_dropped = [], set(), 0
        for u in urns:
            new_path = target_path(u)
            identity = URN.from_parts(to_scheme, new_path)

            owner = existing.get((u.org_id, identity))
            if owner:
                owner_contact_id, kept_urn_id = owner
                if drop_owner_collisions and owner_contact_id == u.contact_id:
                    # the source URN duplicates a URN the same contact already has, so move its references
                    # onto the survivor and drop it
                    u.reassign_content_to(kept_urn_id)
                    u.delete()
                    num_dropped += 1
                    contact_ids.add(u.contact_id)
                continue  # otherwise leave the colliding URN untouched

            u.scheme, u.path, u.identity = to_scheme, new_path, identity
            to_update.append(u)
            if u.contact_id:
                contact_ids.add(u.contact_id)

        if to_update:
            try:
                ContactURN.objects.bulk_update(to_update, ["scheme", "path", "identity"])
            except IntegrityError:
                # a concurrent writer inserted a colliding identity between our check and the update; skip
                # this batch - the command is safe to re-run and will retry it
                self.stdout.write(f"skipped a batch of {len(to_update)} {to_scheme} URNs due to a collision")
                return 0, num_dropped, contact_ids

        return len(to_update), num_dropped, contact_ids

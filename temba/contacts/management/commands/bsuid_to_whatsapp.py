from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.db.models.functions import Now

from temba.contacts.models import URN, Contact, ContactURN

BATCH_SIZE = 1000


class Command(BaseCommand):
    help = (
        "Updates WhatsApp business-scoped user id URNs from the bsuid scheme to the whatsapp scheme, "
        "keeping the path unchanged: bsuid:<CC.alphanumeric> -> whatsapp:<CC.alphanumeric>. "
        "Phone (tel/whatsapp) URNs are never touched - only the bsuid scheme is migrated. "
        "A bsuid URN whose whatsapp target already exists on the same contact is redundant and is dropped "
        "(its message/call/event references are moved onto the existing URN); one colliding with a different "
        "contact in the org is left as-is. Safe to re-run."
    )

    def handle(self, *args, **options):
        num_flipped = num_dropped = 0
        last_id = 0

        while True:
            # process one batch of bsuid URNs, cursoring by id so that skipped (collision) rows and
            # already-migrated rows aren't re-fetched forever
            bsuid_urns = list(
                ContactURN.objects.filter(scheme=URN.BSUID_SCHEME, id__gt=last_id)
                .order_by("id")
                .only("id", "org_id", "path", "contact_id")[:BATCH_SIZE]
            )
            if not bsuid_urns:
                break

            last_id = bsuid_urns[-1].id

            n_flipped, n_dropped, contact_ids = self._flip(bsuid_urns)

            # bump modified_on on changed contacts so the search indexer picks up the change
            if contact_ids:
                Contact.objects.filter(id__in=contact_ids).update(modified_on=Now())

            num_flipped += n_flipped
            num_dropped += n_dropped

        self.stdout.write(f"Migrated {num_flipped} bsuid URNs to whatsapp ({num_dropped} redundant dropped)")

    def _flip(self, urns):
        """
        Flips the given bsuid URNs to the whatsapp scheme, keeping the path unchanged. A URN whose target
        whatsapp identity already exists for the org is a collision and can't be flipped without violating
        the (identity, org) uniqueness constraint. When the colliding identity is held by the *same* contact
        the bsuid URN is redundant, so its message/call/event references are moved onto the existing whatsapp
        URN and the bsuid is deleted; when it's held by a different contact the bsuid is left untouched.

        Returns (num_flipped, num_dropped, {contact_ids}).
        """
        if not urns:
            return 0, 0, set()

        # the whatsapp identity each bsuid would flip to, computed once and reused below
        wa_identities = {u.id: URN.from_parts(URN.WHATSAPP_SCHEME, u.path) for u in urns}

        # existing (org_id, identity) -> (owning contact_id, URN id) for the whatsapp targets, to detect
        # collisions and, for same-contact collisions, find the surviving URN to move references onto
        existing = {
            (org_id, identity): (contact_id, urn_id)
            for org_id, identity, contact_id, urn_id in ContactURN.objects.filter(
                org_id__in={u.org_id for u in urns},
                identity__in=set(wa_identities.values()),
            ).values_list("org_id", "identity", "contact_id", "id")
        }

        # classify each bsuid first without touching the DB, so the whole batch can be applied atomically
        to_flip, to_drop, contact_ids = [], [], set()
        for u in urns:
            identity = wa_identities[u.id]

            owner = existing.get((u.org_id, identity))
            if owner:
                owner_contact_id, kept_urn_id = owner
                if owner_contact_id == u.contact_id:
                    # the bsuid duplicates a whatsapp URN the same contact already has - drop it below
                    to_drop.append((u, kept_urn_id))
                    contact_ids.add(u.contact_id)
                continue  # otherwise leave the colliding bsuid untouched

            u.scheme, u.identity = URN.WHATSAPP_SCHEME, identity
            to_flip.append(u)
            if u.contact_id:
                contact_ids.add(u.contact_id)

        if not to_flip and not to_drop:
            return 0, 0, contact_ids

        try:
            # apply the batch atomically so an IntegrityError leaves nothing partially applied
            with transaction.atomic():
                for u, kept_urn_id in to_drop:
                    # move the redundant bsuid's message/call/event references onto the survivor, then drop it
                    u.reassign_content_to(kept_urn_id)
                    u.delete()
                if to_flip:
                    ContactURN.objects.bulk_update(to_flip, ["scheme", "identity"])
        except IntegrityError:
            # a concurrent writer inserted a colliding identity between our check and the update; the atomic
            # block rolled the whole batch back, so nothing changed here - the command is safe to re-run and
            # will retry these rows
            ids = [u.id for u in urns]
            self.stdout.write(
                f"skipped batch of {len(to_flip)} flips / {len(to_drop)} drops "
                f"(bsuid ids {min(ids)}-{max(ids)}) due to a collision"
            )
            return 0, 0, set()

        return len(to_flip), len(to_drop), contact_ids

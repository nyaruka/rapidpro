from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.db.models.functions import Now

from temba import mailroom
from temba.contacts.models import URN, Contact, ContactURN

BATCH_SIZE = 1000


class Command(BaseCommand):
    help = (
        "Converts legacy bsuid:<CC.xxx> contact URNs to the whatsapp scheme (path unchanged). A bsuid URN whose "
        "whatsapp identity already exists on the same contact is redundant, so its message/call/event references "
        "are moved onto the surviving whatsapp URN and it's deleted. One whose whatsapp identity belongs to a "
        "different contact is left untouched and can be retried by re-running the command."
    )

    def handle(self, *args, **options):
        num_converted = num_dropped = num_skipped = 0
        contacts_changed = set()
        last_id = 0

        while True:
            # process one batch of bsuid URNs, cursoring by id so that skipped (collision) rows aren't
            # re-fetched forever
            batch = list(
                ContactURN.objects.filter(scheme=URN.BSUID_SCHEME, id__gt=last_id)
                .order_by("id")
                .only("id", "org_id", "path", "contact_id", "priority")[:BATCH_SIZE]
            )
            if not batch:
                break

            last_id = batch[-1].id

            converted, dropped, skipped, changed = self._convert(batch)

            # bump modified_on on changed contacts and have mailroom re-index them
            if changed:
                Contact.objects.filter(id__in=changed).update(modified_on=Now())
                self._reindex(changed)

            num_converted += converted
            num_dropped += dropped
            num_skipped += skipped
            contacts_changed |= changed

        self.stdout.write(
            f"Converted {num_converted} bsuid URNs to whatsapp ({num_dropped} redundant dropped, "
            f"{num_skipped} skipped as whatsapp URN belongs to a different contact) "
            f"across {len(contacts_changed)} contacts"
        )

    def _convert(self, urns) -> tuple:
        """
        Converts the given bsuid URNs to the whatsapp scheme, path unchanged. A URN whose target identity already
        exists on the same contact is redundant (courier writes both forms), so its content references are moved
        onto the survivor and it's deleted. One whose target identity is owned by a different contact can't be
        converted without violating the (identity, org) uniqueness constraint, so it's left untouched.

        Returns (num_converted, num_dropped, num_skipped, {ids of changed contacts}).
        """

        # existing (org_id, identity) -> (owning contact_id, URN id), to detect collisions and, for same-contact
        # collisions, find the surviving URN to move references onto
        existing = {
            (org_id, identity): (contact_id, urn_id)
            for org_id, identity, contact_id, urn_id in ContactURN.objects.filter(
                org_id__in={u.org_id for u in urns},
                identity__in={URN.from_parts(URN.WHATSAPP_SCHEME, u.path) for u in urns},
            ).values_list("org_id", "identity", "contact_id", "id")
        }

        # the highest priority all-digit (i.e. phone) whatsapp URN of each contact, so that converted URNs can
        # be kept below it
        phone_priorities = {}
        for contact_id, priority in ContactURN.objects.filter(
            scheme=URN.WHATSAPP_SCHEME,
            contact_id__in={u.contact_id for u in urns if u.contact_id},
            path__regex=r"^[0-9]+$",
        ).values_list("contact_id", "priority"):
            if priority > phone_priorities.get(contact_id, -1):
                phone_priorities[contact_id] = priority

        to_update, changed, num_dropped, num_skipped = [], set(), 0, 0
        for u in urns:
            identity = URN.from_parts(URN.WHATSAPP_SCHEME, u.path)

            owner = existing.get((u.org_id, identity))
            if owner:
                owner_contact_id, kept_urn_id = owner
                if owner_contact_id == u.contact_id:
                    # the bsuid URN duplicates a whatsapp URN the same contact already has, so move its
                    # references (all on_delete=PROTECT) onto the survivor and drop it
                    u.msgs.update(contact_urn_id=kept_urn_id)
                    u.calls.update(contact_urn_id=kept_urn_id)
                    u.channel_events.update(contact_urn_id=kept_urn_id)
                    u.delete()
                    num_dropped += 1
                    if u.contact_id:
                        changed.add(u.contact_id)
                else:
                    num_skipped += 1
                continue

            u.scheme, u.identity = URN.WHATSAPP_SCHEME, identity

            # a converted URN mustn't outrank the contact's phone whatsapp URN
            phone_priority = phone_priorities.get(u.contact_id)
            if phone_priority is not None and phone_priority <= u.priority:
                u.priority = phone_priority - 1

            to_update.append(u)

        if to_update:
            try:
                ContactURN.objects.bulk_update(to_update, ["scheme", "identity", "priority"])
            except IntegrityError:
                # a concurrent writer inserted a colliding identity between our check and the update; skip
                # this batch - the command is safe to re-run and will retry it
                self.stdout.write(f"skipped a batch of {len(to_update)} URNs due to a collision")
                return 0, num_dropped, num_skipped, changed

        changed.update(u.contact_id for u in to_update if u.contact_id)

        return len(to_update), num_dropped, num_skipped, changed

    def _reindex(self, contact_ids):
        """
        Tells mailroom to re-index the given contacts in search.
        """
        by_org = defaultdict(list)
        for contact in Contact.objects.filter(id__in=contact_ids).select_related("org"):
            by_org[contact.org].append(contact)

        client = mailroom.get_client()
        for org, contacts in by_org.items():
            client.contact_reindex(org, contacts)

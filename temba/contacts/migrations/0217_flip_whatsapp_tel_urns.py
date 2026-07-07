from django.db import migrations
from django.db.models.functions import Now

BATCH_SIZE = 1000


def _flip_scheme(ContactURN, Contact, *, from_scheme, to_scheme, add_plus, digits_only=False):
    """
    Flips one URN scheme to another in id-ordered batches, skipping any row whose target identity
    already exists for the org (to avoid violating the (identity, org) uniqueness constraint). Contacts
    with a flipped URN have their modified_on bumped so the search indexer picks up the change.

    Batching uses an id cursor rather than re-querying the head of the filter because skipped collision
    rows keep their original scheme and would otherwise be re-fetched forever.

    When digits_only is set, only rows whose path is entirely digits are flipped. This keeps the whatsapp
    -> tel flip safe to run more than once: after a run, whatsapp rows hold business-scoped ids (e.g.
    RW.abc123) which aren't all-digit and so are left alone on any re-run.
    """

    def target(urn):
        path = ("+" + urn.path) if add_plus else urn.path
        return f"{to_scheme}:{path}"

    num_flipped = 0
    last_id = 0

    while True:
        query = ContactURN.objects.filter(scheme=from_scheme, id__gt=last_id)
        if digits_only:
            query = query.filter(path__regex=r"^[0-9]+$")

        batch = list(query.order_by("id").only("id", "org_id", "path", "contact_id")[:BATCH_SIZE])
        if not batch:
            break

        last_id = batch[-1].id  # advance past every row we looked at, including any we skip

        # find which target identities already exist so we can skip those rows
        existing = set(
            ContactURN.objects.filter(identity__in={target(u) for u in batch}).values_list("org_id", "identity")
        )

        to_update, contact_ids = [], set()
        for u in batch:
            identity = target(u)
            if (u.org_id, identity) in existing:
                continue  # collision - leave untouched

            u.scheme = to_scheme
            if add_plus:
                u.path = "+" + u.path
            u.identity = identity
            to_update.append(u)
            if u.contact_id:
                contact_ids.add(u.contact_id)

        if to_update:
            ContactURN.objects.bulk_update(to_update, ["scheme", "path", "identity"])
            Contact.objects.filter(id__in=contact_ids).update(modified_on=Now())
            num_flipped += len(to_update)

    print(f"Flipped {num_flipped} {from_scheme} URNs to {to_scheme}")


def flip_whatsapp_tel_urns(apps, schema_editor):
    """
    Flips existing WhatsApp channel URNs to match the new scheme model:
      * whatsapp:<e164 digits>  ->  tel:+<e164 digits>   (the phone identity)
      * bsuid:<CC.alphanumeric> ->  whatsapp:<CC.alphanumeric>  (the business-scoped user id)

    URNs whose target identity already exists for the org are left untouched to avoid violating the
    (identity, org) uniqueness constraint - they can't be safely deleted as they may be referenced by
    messages/calls.

    Only all-digit whatsapp paths are flipped to tel, so the migration is safe to apply more than once:
    after a run the whatsapp scheme holds business-scoped ids (CC.alphanumeric) which are skipped, and
    there are no bsuid rows left to flip.
    """

    ContactURN = apps.get_model("contacts", "ContactURN")
    Contact = apps.get_model("contacts", "Contact")

    _flip_scheme(ContactURN, Contact, from_scheme="whatsapp", to_scheme="tel", add_plus=True, digits_only=True)
    _flip_scheme(ContactURN, Contact, from_scheme="bsuid", to_scheme="whatsapp", add_plus=False)


def apply_manual():  # pragma: no cover
    from django.apps import apps

    flip_whatsapp_tel_urns(apps, None)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("contacts", "0216_remove_contact_contacts_contact_org_modified_and_more"),
    ]

    operations = [
        migrations.RunPython(flip_whatsapp_tel_urns, migrations.RunPython.noop),
    ]

from django.db import connection as default_connection, migrations


def flip_whatsapp_tel_urns(apps, schema_editor):
    """
    Flips existing WhatsApp channel URNs to match the new scheme model:
      * whatsapp:<e164 digits>  ->  tel:+<e164 digits>   (the phone identity)
      * bsuid:<CC.alphanumeric> ->  whatsapp:<CC.alphanumeric>  (the business-scoped user id)

    URNs whose target identity already exists for the org are left untouched to avoid violating the
    (identity, org) uniqueness constraint - they can't be safely deleted as they may be referenced by
    messages/calls. Affected contacts have their modified_on bumped so the search indexer picks up the
    change.
    """

    connection = schema_editor.connection if schema_editor is not None else default_connection

    with connection.cursor() as cursor:
        # whatsapp -> tel (add the leading + that tel URNs require), then reindex affected contacts
        cursor.execute(
            """
            WITH flipped AS (
                UPDATE contacts_contacturn u
                   SET scheme = 'tel', path = '+' || u.path, identity = 'tel:+' || u.path
                 WHERE u.scheme = 'whatsapp'
                   AND NOT EXISTS (
                       SELECT 1 FROM contacts_contacturn t
                        WHERE t.org_id = u.org_id AND t.identity = 'tel:+' || u.path AND t.id <> u.id
                   )
                RETURNING u.contact_id
            ), reindexed AS (
                UPDATE contacts_contact c
                   SET modified_on = clock_timestamp()
                  FROM (SELECT DISTINCT contact_id FROM flipped WHERE contact_id IS NOT NULL) f
                 WHERE c.id = f.contact_id
                RETURNING c.id
            )
            SELECT (SELECT count(*) FROM flipped), (SELECT count(*) FROM reindexed)
            """
        )
        wa_flipped, wa_reindexed = cursor.fetchone()

        # bsuid -> whatsapp (path is unchanged), then reindex affected contacts
        cursor.execute(
            """
            WITH flipped AS (
                UPDATE contacts_contacturn u
                   SET scheme = 'whatsapp', identity = 'whatsapp:' || u.path
                 WHERE u.scheme = 'bsuid'
                   AND NOT EXISTS (
                       SELECT 1 FROM contacts_contacturn t
                        WHERE t.org_id = u.org_id AND t.identity = 'whatsapp:' || u.path AND t.id <> u.id
                   )
                RETURNING u.contact_id
            ), reindexed AS (
                UPDATE contacts_contact c
                   SET modified_on = clock_timestamp()
                  FROM (SELECT DISTINCT contact_id FROM flipped WHERE contact_id IS NOT NULL) f
                 WHERE c.id = f.contact_id
                RETURNING c.id
            )
            SELECT (SELECT count(*) FROM flipped), (SELECT count(*) FROM reindexed)
            """
        )
        bsuid_flipped, bsuid_reindexed = cursor.fetchone()

    print(f"Flipped {wa_flipped} whatsapp URNs to tel (reindexed {wa_reindexed} contacts)")
    print(f"Flipped {bsuid_flipped} bsuid URNs to whatsapp (reindexed {bsuid_reindexed} contacts)")


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

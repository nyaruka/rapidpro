from django.db import connection as default_connection, migrations
from django.db.models import Max, Min

# Msg.folder is denormalized from direction/visibility/status/flow and is written by mailroom and courier for new
# messages - this fills it in for the messages that predate that. The CASE mirrors Msg.derive_folder, including its
# precedence: being deleted, and then being unhandled, both come before the user facing folders, so that a message
# which is archived or deleted whilst still pending doesn't land in Archived.
#
# The branches are exhaustive over the states the database allows, because the temba_msg_on_change trigger rejects
# the only two combinations that would otherwise fall through - an incoming message that isn't pending or handled,
# and an outgoing message that is archived. Should one somehow exist, it keeps its null folder.
#
# The table is far too large to scan for null folders, so we walk the primary key range in batches instead, newest
# first so that the messages users are most likely to be looking at are filled in first. Each batch is its own
# transaction, so an interrupted run can be resumed from the last id it reported.

BATCH_SIZE = 1_000_000  # ids per batch, not rows - ids are sparse wherever messages have been deleted

SQL_BACKFILL_FOLDER = """
UPDATE msgs_msg SET folder = CASE
    WHEN visibility IN ('D', 'X') THEN 'D'                                                   -- deleted
    WHEN direction = 'I' AND status = 'P' THEN 'P'                                           -- pending
    WHEN direction = 'I' AND visibility = 'V' AND status = 'H' AND flow_id IS NULL THEN 'I'  -- inbox
    WHEN direction = 'I' AND visibility = 'V' AND status = 'H' THEN 'W'                      -- handled
    WHEN direction = 'I' AND visibility = 'A' AND status = 'H' THEN 'A'                      -- archived
    WHEN direction = 'O' AND visibility = 'V' AND status IN ('I', 'Q', 'E') THEN 'O'         -- outbox
    WHEN direction = 'O' AND visibility = 'V' AND status IN ('W', 'S', 'D', 'R') THEN 'S'    -- sent
    WHEN direction = 'O' AND visibility = 'V' AND status = 'F' THEN 'X'                      -- failed
END
WHERE id >= %(low)s AND id <= %(high)s AND folder IS NULL
"""


def backfill_msg_folder(apps, schema_editor):
    Msg = apps.get_model("msgs", "Msg")

    # schema_editor is None when this is run out of band via apply_manual
    conn = schema_editor.connection if schema_editor else default_connection

    id_range = Msg.objects.aggregate(low=Min("id"), high=Max("id"))
    lowest, highest = id_range["low"], id_range["high"]
    if lowest is None:  # no messages at all
        return

    num_updated = 0
    batch_high = highest

    while batch_high >= lowest:
        batch_low = max(batch_high - BATCH_SIZE + 1, lowest)

        with conn.cursor() as cursor:
            cursor.execute(SQL_BACKFILL_FOLDER, {"low": batch_low, "high": batch_high})
            num_updated += cursor.rowcount

        print(f"Backfilled folder on {num_updated} messages (down to id={batch_low})")

        batch_high = batch_low - 1


def apply_manual():  # pragma: no cover
    from django.apps import apps

    backfill_msg_folder(apps, None)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("msgs", "0309_msg_folder"),
    ]

    operations = [
        migrations.RunPython(backfill_msg_folder, migrations.RunPython.noop),
    ]

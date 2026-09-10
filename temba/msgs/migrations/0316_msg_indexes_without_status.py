from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models
from django.db.migrations.operations.models import AddIndex


class AddIndexConcurrentlyPlainReverse(AddIndexConcurrently):
    """
    Adds the index concurrently but reverses with a plain drop, so that migration tests - which roll the graph
    backwards inside a transaction - can unapply it.
    """

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        AddIndex.database_backwards(self, app_label, schema_editor, from_state, to_state)


class Migration(migrations.Migration):
    # Postgres can only make a heap-only (HOT) update when none of the columns actually changed are referenced by any
    # index on the table - including columns that only appear in a partial index's WHERE. The two partial indexes on
    # outgoing messages both have status in their predicates, so every status change on a message has to update every
    # index on the table, even when nothing it changed is indexed. These replace them with indexes whose predicates
    # don't reference status:
    #
    #   - the retry index is on next_attempt being set, which is only the case whilst a message is awaiting a retry.
    #     That's already how mailroom writes it, and courier now clears it whenever a message moves on (see
    #     0317 for the messages written before that).
    #   - the Android index is on the outbox folder, which is exactly the visible outgoing messages still waiting to
    #     be sent, i.e. the statuses the old predicate listed.
    #
    # They're added under new names so that they can be built without a gap in coverage - the old ones are dropped in
    # 0318 - and because an index build on the messages table can't hold ACCESS EXCLUSIVE for its duration, they're
    # created concurrently. Installations large enough to care can build them by hand ahead of the deploy and fake
    # this migration:
    #
    #   CREATE INDEX CONCURRENTLY msgs_outgoing_awaiting_retry ON msgs_msg (next_attempt, created_on, id)
    #   WHERE direction = 'O' AND next_attempt IS NOT NULL;
    #   CREATE INDEX CONCURRENTLY msgs_android_outbox ON msgs_msg (created_on)
    #   WHERE direction = 'O' AND is_android AND folder = 'O';
    #
    atomic = False

    dependencies = [
        ("msgs", "0315_update_triggers"),
    ]

    operations = [
        AddIndexConcurrentlyPlainReverse(
            model_name="msg",
            index=models.Index(
                name="msgs_outgoing_awaiting_retry",
                fields=["next_attempt", "created_on", "id"],
                condition=models.Q(("direction", "O"), ("next_attempt__isnull", False)),
            ),
        ),
        AddIndexConcurrentlyPlainReverse(
            model_name="msg",
            index=models.Index(
                name="msgs_android_outbox",
                fields=["created_on"],
                condition=models.Q(("direction", "O"), ("folder", "O"), ("is_android", True)),
            ),
        ),
    ]

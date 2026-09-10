from django.contrib.postgres.operations import RemoveIndexConcurrently
from django.db import migrations
from django.db.migrations.operations.models import RemoveIndex


class RemoveIndexConcurrentlyPlainReverse(RemoveIndexConcurrently):
    """
    Removes the index concurrently but reverses with a plain create, so that migration tests - which roll the graph
    backwards inside a transaction - can unapply it.
    """

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        RemoveIndex.database_backwards(self, app_label, schema_editor, from_state, to_state)


class Migration(migrations.Migration):
    # the indexes replaced in 0316 - dropped once their replacements exist so that the queries they serve are never
    # without an index. The queries which used these already satisfy the predicates of the replacements, so nothing
    # has to be deployed in between.
    atomic = False

    dependencies = [
        ("msgs", "0317_backfill_msg_next_attempt"),
    ]

    operations = [
        RemoveIndexConcurrentlyPlainReverse(model_name="msg", name="msgs_outgoing_to_retry"),
        RemoveIndexConcurrentlyPlainReverse(model_name="msg", name="msgs_outgoing_android_to_fail"),
    ]

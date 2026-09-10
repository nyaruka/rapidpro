from django.db import migrations


class Migration(migrations.Migration):
    # a heap-only (HOT) update needs room on the same page for the new row version, and by default pages are packed
    # full. Leaving some free space on each page gives the status updates a message receives after being sent - which
    # 0316 made HOT-eligible - somewhere to go, at the cost of a slightly larger heap. Note that this only affects how
    # pages are filled from now on: existing pages aren't rewritten, so the benefit arrives with new messages, which
    # is where the updates happen anyway.
    dependencies = [
        ("msgs", "0318_remove_msg_status_indexes"),
    ]

    operations = [
        migrations.RunSQL(
            "ALTER TABLE msgs_msg SET (fillfactor = 90)",
            reverse_sql="ALTER TABLE msgs_msg RESET (fillfactor)",
        ),
    ]

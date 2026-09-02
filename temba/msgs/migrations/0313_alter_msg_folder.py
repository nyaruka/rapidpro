from django.db import migrations, models

# On a large table this is better done ahead of the deploy, as a CHECK (folder IS NOT NULL) constraint added NOT VALID,
# validated (which scans without blocking writes), then SET NOT NULL - which Postgres satisfies from the validated
# constraint without another scan, and which this migration then finds already in place and skips.


class Migration(migrations.Migration):
    dependencies = [
        ("msgs", "0312_remove_msg_msgs_inbox_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="msg",
            name="folder",
            field=models.CharField(
                choices=[
                    ("I", "Inbox"),
                    ("W", "Handled"),
                    ("A", "Archived"),
                    ("O", "Outbox"),
                    ("S", "Sent"),
                    ("X", "Failed"),
                    ("P", "Pending"),
                    ("D", "Deleted"),
                ],
                max_length=1,
            ),
        ),
    ]

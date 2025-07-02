# This is a dummy migration which will be implemented in the next release

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("orgs", "0171_squashed"),
        ("schedules", "0029_alter_schedule_repeat_period"),
    ]

    operations = []

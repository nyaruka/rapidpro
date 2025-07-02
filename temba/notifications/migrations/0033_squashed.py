# This is a dummy migration which will be implemented in the next release

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("channels", "0206_squashed"),
        ("notifications", "0032_alter_notification_email_status"),
    ]

    operations = []

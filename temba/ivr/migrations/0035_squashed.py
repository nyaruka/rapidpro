# This is a dummy migration which will be implemented in the next release

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("channels", "0206_squashed"),
        ("contacts", "0207_squashed"),
        ("ivr", "0034_call_uuid"),
    ]

    operations = []

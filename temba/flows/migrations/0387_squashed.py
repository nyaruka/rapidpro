# This is a dummy migration which will be implemented in the next release

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("channels", "0206_squashed"),
        ("classifiers", "0016_squashed"),
        ("flows", "0386_remove_flowstart_calls_and_more"),
    ]

    operations = []

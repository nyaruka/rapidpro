# This is a dummy migration which will be implemented in the next release

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("contacts", "0207_squashed"),
        ("msgs", "0287_remove_msg_metadata"),
    ]

    operations = []

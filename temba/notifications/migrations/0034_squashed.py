# This is a dummy migration which will be implemented in the next release

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("contacts", "0207_squashed"),
        ("notifications", "0033_squashed"),
        ("orgs", "0171_squashed"),
    ]

    operations = []

# This is a dummy migration which will be implemented in the next release

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("airtime", "0036_squashed"),
        ("orgs", "0171_squashed"),
    ]

    operations = []

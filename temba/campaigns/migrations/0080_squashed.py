# This is a dummy migration which will be implemented in the next release

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0079_squashed"),
        ("contacts", "0207_squashed"),
        ("flows", "0387_squashed"),
        ("orgs", "0171_squashed"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = []

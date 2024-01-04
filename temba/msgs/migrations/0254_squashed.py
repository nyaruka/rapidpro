# This is a dummy migration which will be implemented in the next release

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tickets", "0057_squashed"),
        ("orgs", "0133_squashed"),
        ("contacts", "0184_squashed"),
        ("channels", "0182_squashed"),
        ("flows", "0330_squashed"),
        ("schedules", "0027_squashed"),
        ("msgs", "0253_squashed"),
    ]

    operations = []
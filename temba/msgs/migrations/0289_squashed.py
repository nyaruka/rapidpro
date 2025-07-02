# This is a dummy migration which will be implemented in the next release

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("channels", "0207_squashed"),
        ("contacts", "0208_squashed"),
        ("flows", "0388_squashed"),
        ("msgs", "0288_squashed"),
        ("orgs", "0171_squashed"),
        ("schedules", "0030_squashed"),
        ("templates", "0046_squashed"),
        ("tickets", "0078_squashed"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = []

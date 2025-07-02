# This is a dummy migration which will be implemented in the next release

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("contacts", "0208_squashed"),
        ("flows", "0388_squashed"),
        ("orgs", "0172_squashed"),
        ("tickets", "0078_squashed"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = []

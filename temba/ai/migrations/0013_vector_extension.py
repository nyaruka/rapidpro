# This migration is hand-written and must be preserved when squashing — the extension has no model
# representation so a regenerated squash would silently drop it. Creating the extension requires
# superuser (or rds_superuser-equivalent); deployments whose migration user lacks that privilege
# must pre-create the extension out-of-band (the operation is CREATE EXTENSION IF NOT EXISTS).
from pgvector.django import VectorExtension

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ai", "0012_deepseek_model"),
    ]

    operations = [
        VectorExtension(),
    ]

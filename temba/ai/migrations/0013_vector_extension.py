# This migration is hand-written and must be preserved when squashing — the extension has no model
# representation so a regenerated squash would silently drop it. Creating the extension requires
# superuser (or rds_superuser-equivalent); deployments whose migration user lacks that privilege
# must pre-create the extension out-of-band (the operation is CREATE EXTENSION IF NOT EXISTS).
from pgvector.django import VectorExtension

from django.db import migrations


def check_vector_version(apps, schema_editor):  # pragma: no cover
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        version = cursor.fetchone()[0]

    if tuple(int(p) for p in version.split(".")[:2]) < (0, 8):
        raise Exception(f"pgvector extension >= 0.8 is required (found {version})")


class Migration(migrations.Migration):
    dependencies = [
        ("ai", "0012_deepseek_model"),
    ]

    operations = [
        VectorExtension(),
        migrations.RunPython(check_vector_version, migrations.RunPython.noop),
    ]

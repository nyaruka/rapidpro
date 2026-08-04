# The VectorExtension operation and its version guard below are hand-written and must be preserved
# when squashing - the extension has no model representation, so a regenerated squash would silently
# drop it and every vector column with it. Creating the extension requires superuser (or the
# rds_superuser equivalent); deployments whose migration user lacks that privilege must pre-create it
# out of band, which is safe because the operation is CREATE EXTENSION IF NOT EXISTS.
import pgvector.django.indexes
import pgvector.django.vector
from pgvector.django import VectorExtension

import django.db.models.deletion
import django.db.models.functions.text
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import temba.utils.fields
import temba.utils.uuid


def check_vector_version(apps, schema_editor):  # pragma: no cover
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        version = cursor.fetchone()[0]

    if tuple(int(p) for p in version.split(".")[:2]) < (0, 8):
        raise Exception(f"pgvector extension >= 0.8 is required (found {version})")


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("orgs", "0188_reset_dropped_languages"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        VectorExtension(),
        migrations.RunPython(check_vector_version, migrations.RunPython.noop),
        migrations.CreateModel(
            name="Article",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("uuid", models.UUIDField(default=temba.utils.uuid.uuid4, unique=True)),
                ("sort_order", models.IntegerField(default=0)),
                ("title", models.CharField(max_length=255)),
                ("slug", models.SlugField(max_length=255)),
                ("body", models.TextField(default="")),
                (
                    "status",
                    models.CharField(
                        choices=[("D", "Draft"), ("P", "Published")],
                        default="D",
                        max_length=1,
                    ),
                ),
                ("published_on", models.DateTimeField(null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_on", models.DateTimeField(default=django.utils.timezone.now)),
                ("modified_on", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "modified_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="knowledge.article",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ArticleImage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("uuid", models.UUIDField(default=temba.utils.uuid.uuid4, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("path", models.CharField(max_length=2048)),
                ("content_type", models.CharField(max_length=255)),
                ("size", models.IntegerField()),
                ("created_on", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "article",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="images",
                        to="knowledge.article",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Knowledge",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this item is active, use this instead of deleting",
                    ),
                ),
                (
                    "created_on",
                    models.DateTimeField(
                        blank=True,
                        default=django.utils.timezone.now,
                        editable=False,
                        help_text="When this item was originally created",
                    ),
                ),
                (
                    "modified_on",
                    models.DateTimeField(
                        blank=True,
                        default=django.utils.timezone.now,
                        editable=False,
                        help_text="When this item was last modified",
                    ),
                ),
                ("uuid", models.UUIDField(default=temba.utils.uuid.uuid4, unique=True)),
                (
                    "name",
                    models.CharField(max_length=64, validators=[temba.utils.fields.NameValidator(64)]),
                ),
                ("is_system", models.BooleanField(default=False)),
                (
                    "knowledge_type",
                    models.CharField(
                        choices=[
                            ("shortcuts", "Shortcuts"),
                            ("helpdesk", "Helpdesk"),
                            ("website", "Website"),
                            ("documents", "Documents"),
                        ],
                        max_length=16,
                    ),
                ),
                ("config", models.JSONField(default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("P", "Pending"),
                            ("I", "Indexing"),
                            ("R", "Ready"),
                            ("F", "Failed"),
                        ],
                        default="P",
                        max_length=1,
                    ),
                ),
                ("error", models.CharField(max_length=255, null=True)),
                ("last_indexed_on", models.DateTimeField(null=True)),
                ("num_items", models.IntegerField(default=0)),
                ("num_chunks", models.IntegerField(default=0)),
                (
                    "created_by",
                    models.ForeignKey(
                        help_text="The user which originally created this item",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_creations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "modified_by",
                    models.ForeignKey(
                        help_text="The user which last modified this item",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_modifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "org",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="knowledge",
                        to="orgs.org",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="article",
            name="knowledge",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="articles",
                to="knowledge.knowledge",
            ),
        ),
        migrations.CreateModel(
            name="KnowledgeChunk",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("item_key", models.UUIDField()),
                ("item_name", models.CharField(max_length=255)),
                ("item_url", models.URLField(max_length=2048, null=True)),
                ("text", models.TextField()),
                ("embedding", pgvector.django.vector.VectorField(dimensions=384)),
                (
                    "knowledge",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="chunks",
                        to="knowledge.knowledge",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="KnowledgeItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("uuid", models.UUIDField(default=temba.utils.uuid.uuid4, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("url", models.URLField(max_length=2048, null=True)),
                ("path", models.CharField(max_length=2048, null=True)),
                ("content_type", models.CharField(max_length=255)),
                ("size", models.IntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("P", "Pending"),
                            ("I", "Indexing"),
                            ("R", "Ready"),
                            ("F", "Failed"),
                        ],
                        default="P",
                        max_length=1,
                    ),
                ),
                ("error", models.CharField(max_length=255, null=True)),
                ("num_chunks", models.IntegerField(default=0)),
                ("created_on", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "knowledge",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="items",
                        to="knowledge.knowledge",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="knowledge",
            index=models.Index(
                condition=models.Q(("is_active", True), ("status", "P")),
                fields=["id"],
                name="knowledge_pending",
            ),
        ),
        migrations.AddConstraint(
            model_name="knowledge",
            constraint=models.UniqueConstraint(
                models.F("org"),
                django.db.models.functions.text.Lower("name"),
                name="unique_knowledge_names",
            ),
        ),
        migrations.AddIndex(
            model_name="article",
            index=models.Index(fields=["knowledge", "parent", "sort_order"], name="article_by_tree"),
        ),
        migrations.AddIndex(
            model_name="article",
            index=models.Index(fields=["knowledge", "modified_on"], name="article_by_modified"),
        ),
        migrations.AddConstraint(
            model_name="article",
            constraint=models.UniqueConstraint(
                models.F("knowledge"),
                models.F("slug"),
                condition=models.Q(("is_active", True)),
                name="unique_article_slugs",
            ),
        ),
        migrations.AddIndex(
            model_name="knowledgechunk",
            index=pgvector.django.indexes.HnswIndex(
                ef_construction=64,
                fields=["embedding"],
                m=16,
                name="knowledgechunk_embedding",
                opclasses=("vector_cosine_ops",),
            ),
        ),
        migrations.AddIndex(
            model_name="knowledgechunk",
            index=models.Index(fields=["knowledge", "item_key"], name="knowledgechunk_by_item"),
        ),
        migrations.AddConstraint(
            model_name="knowledgeitem",
            constraint=models.UniqueConstraint(
                models.F("knowledge"),
                models.F("url"),
                name="unique_knowledge_item_urls",
            ),
        ),
    ]

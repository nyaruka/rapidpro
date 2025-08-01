# Generated by Django 5.2.2 on 2025-07-02 14:48

import django.db.models.deletion
import django.db.models.functions.text
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("ai", "0006_squashed"),
        ("orgs", "0171_squashed"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="llm",
            name="created_by",
            field=models.ForeignKey(
                help_text="The user which originally created this item",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="%(app_label)s_%(class)s_creations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="llm",
            name="modified_by",
            field=models.ForeignKey(
                help_text="The user which last modified this item",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="%(app_label)s_%(class)s_modifications",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="llm",
            name="org",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="llms",
                to="orgs.org",
            ),
        ),
        migrations.AddConstraint(
            model_name="llm",
            constraint=models.UniqueConstraint(
                models.F("org"),
                django.db.models.functions.text.Lower("name"),
                name="unique_llm_names",
            ),
        ),
    ]

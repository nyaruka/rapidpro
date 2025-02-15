# Generated by Django 5.1.4 on 2025-01-06 21:25

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("ivr", "0030_squashed"),
        ("orgs", "0162_squashed"),
    ]

    operations = [
        migrations.AddField(
            model_name="call",
            name="org",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="calls",
                to="orgs.org",
            ),
        ),
        migrations.AddIndex(
            model_name="call",
            index=models.Index(fields=["org", "-created_on"], name="calls_org_created_on"),
        ),
        migrations.AddIndex(
            model_name="call",
            index=models.Index(
                condition=models.Q(("next_attempt__isnull", False), ("status__in", ("Q", "E"))),
                fields=["next_attempt"],
                name="calls_to_retry",
            ),
        ),
    ]

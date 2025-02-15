# Generated by Django 5.1.4 on 2025-02-11 20:37

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import temba.utils.text


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_ensure_anon_user"),
        ("orgs", "0167_alter_backuptoken_user"),
    ]

    operations = [
        migrations.CreateModel(
            name="BackupToken",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(default=temba.utils.text.generate_token, max_length=18, unique=True)),
                ("is_used", models.BooleanField(default=False)),
                ("created_on", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="backup_tokens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]

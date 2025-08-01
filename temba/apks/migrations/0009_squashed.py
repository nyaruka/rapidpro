# Generated by Django 5.2.2 on 2025-07-02 14:48

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Apk",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "apk_type",
                    models.CharField(
                        choices=[
                            ("R", "Relayer Application APK"),
                            ("M", "Message Pack Application APK"),
                        ],
                        max_length=1,
                    ),
                ),
                ("apk_file", models.FileField(upload_to="apks")),
                ("version", models.TextField(help_text="Our version, ex: 1.9.8")),
                (
                    "pack",
                    models.IntegerField(
                        blank=True,
                        help_text="Our pack number if this is a message pack (otherwise blank)",
                        null=True,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Changelog for this version, markdown supported",
                        null=True,
                    ),
                ),
                ("created_on", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                "unique_together": {("apk_type", "version", "pack")},
            },
        ),
    ]

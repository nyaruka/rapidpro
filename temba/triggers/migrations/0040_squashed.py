# Generated by Django 4.2.8 on 2024-01-05 15:09

import django.contrib.postgres.fields
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("orgs", "0133_squashed"),
        ("contacts", "0183_squashed"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("schedules", "0027_squashed"),
        ("flows", "0329_squashed"),
        ("channels", "0181_squashed"),
    ]

    operations = [
        migrations.CreateModel(
            name="Trigger",
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
                ("trigger_type", models.CharField(default="K", max_length=1)),
                ("is_archived", models.BooleanField(default=False)),
                ("priority", models.IntegerField()),
                (
                    "keywords",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(max_length=16), null=True, size=None
                    ),
                ),
                (
                    "match_type",
                    models.CharField(
                        choices=[
                            ("F", "Message starts with the keyword"),
                            ("O", "Message contains only the keyword"),
                        ],
                        max_length=1,
                        null=True,
                    ),
                ),
                ("referrer_id", models.CharField(max_length=255, null=True)),
                (
                    "channel",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="triggers",
                        to="channels.channel",
                    ),
                ),
                (
                    "contacts",
                    models.ManyToManyField(related_name="triggers", to="contacts.contact"),
                ),
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
                    "exclude_groups",
                    models.ManyToManyField(related_name="triggers_excluded", to="contacts.contactgroup"),
                ),
                (
                    "flow",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="triggers",
                        to="flows.flow",
                    ),
                ),
                (
                    "groups",
                    models.ManyToManyField(related_name="triggers_included", to="contacts.contactgroup"),
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
                        related_name="triggers",
                        to="orgs.org",
                    ),
                ),
                (
                    "schedule",
                    models.OneToOneField(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="trigger",
                        to="schedules.schedule",
                    ),
                ),
            ],
            options={
                "verbose_name": "Trigger",
                "verbose_name_plural": "Triggers",
            },
        ),
        migrations.AddConstraint(
            model_name="trigger",
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(("trigger_type", "S"), _negated=True),
                    ("schedule__isnull", False),
                    ("is_active", False),
                    _connector="OR",
                ),
                name="triggers_scheduled_trigger_has_schedule",
            ),
        ),
    ]

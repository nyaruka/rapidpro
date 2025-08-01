# Generated by Django 5.2.2 on 2025-07-02 14:48

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("airtime", "0036_squashed"),
        ("channels", "0206_squashed"),
        ("flows", "0387_squashed"),
        ("orgs", "0171_squashed"),
    ]

    operations = [
        migrations.CreateModel(
            name="HTTPLog",
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
                    "log_type",
                    models.CharField(
                        choices=[
                            ("webhook_called", "Webhook Called"),
                            ("airtime_transferred", "Airtime Transferred"),
                            ("whatsapp_templates_synced", "WhatsApp Templates Synced"),
                            ("whatsapp_tokens_synced", "WhatsApp Tokens Synced"),
                            (
                                "whatsapp_contacts_refreshed",
                                "WhatsApp Contacts Refreshed",
                            ),
                            ("whataspp_check_health", "WhatsApp Health Check"),
                        ],
                        max_length=32,
                    ),
                ),
                ("url", models.URLField(max_length=2048)),
                ("status_code", models.IntegerField(default=0, null=True)),
                ("request", models.TextField()),
                ("response", models.TextField(null=True)),
                ("request_time", models.IntegerField()),
                ("num_retries", models.IntegerField(default=0, null=True)),
                ("created_on", models.DateTimeField(default=django.utils.timezone.now)),
                ("is_error", models.BooleanField()),
                (
                    "airtime_transfer",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="http_logs",
                        to="airtime.airtimetransfer",
                    ),
                ),
                (
                    "channel",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="http_logs",
                        to="channels.channel",
                    ),
                ),
                (
                    "flow",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="http_logs",
                        to="flows.flow",
                    ),
                ),
                (
                    "org",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="http_logs",
                        to="orgs.org",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        condition=models.Q(("flow__isnull", False)),
                        fields=["org", "-created_on"],
                        name="httplog_org_flows_only",
                    ),
                    models.Index(
                        condition=models.Q(("flow__isnull", False), ("is_error", True)),
                        fields=["org", "-created_on"],
                        name="httplog_org_flows_only_error",
                    ),
                ],
            },
        ),
    ]

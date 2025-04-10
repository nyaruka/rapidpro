# Generated by Django 5.1.4 on 2025-04-02 16:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("request_logs", "0019_squashed"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="httplog",
            name="request_log_classif_8a1320_idx",
        ),
        migrations.RemoveField(
            model_name="httplog",
            name="classifier",
        ),
        migrations.AlterField(
            model_name="httplog",
            name="log_type",
            field=models.CharField(
                choices=[
                    ("webhook_called", "Webhook Called"),
                    ("airtime_transferred", "Airtime Transferred"),
                    ("whatsapp_templates_synced", "WhatsApp Templates Synced"),
                    ("whatsapp_tokens_synced", "WhatsApp Tokens Synced"),
                    ("whatsapp_contacts_refreshed", "WhatsApp Contacts Refreshed"),
                    ("whataspp_check_health", "WhatsApp Health Check"),
                ],
                max_length=32,
            ),
        ),
    ]

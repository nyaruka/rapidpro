# Generated by Django 5.1.9 on 2025-05-13 15:10

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0014_remove_backuptoken_user_delete_failedlogin_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="email_status",
        ),
        migrations.RemoveField(
            model_name="user",
            name="email_verification_secret",
        ),
        migrations.RemoveField(
            model_name="user",
            name="two_factor_enabled",
        ),
        migrations.RemoveField(
            model_name="user",
            name="two_factor_secret",
        ),
    ]

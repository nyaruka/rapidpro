# Generated by Django 5.0.4 on 2024-06-07 18:20

import secrets

from django.db import migrations


def backfill_email_verification_secret(apps, schema_editor):  # pragma: no cover
    User = apps.get_model("orgs", "User")

    def generate_secret() -> str:
        return "".join([secrets.choice("23456789ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(64)])

    for user in User.objects.filter(settings__email_verification_secret=None):
        user.settings.email_verification_secret = generate_secret()
        user.settings.save(update_fields=("email_verification_secret",))


def reverse(apps, schema_editor):  # pragma: no cover
    pass


class Migration(migrations.Migration):

    dependencies = [("orgs", "0142_alter_usersettings_user")]

    operations = [migrations.RunPython(backfill_email_verification_secret, reverse)]

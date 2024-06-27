# Generated by Django 5.0.4 on 2024-05-16 18:05

from django.db import migrations


def backfill_proxy_fields(apps, schema_editor):
    ContactField = apps.get_model("contacts", "ContactField")

    # delete all old system fields that weren't usable
    num_deleted, _ = (
        ContactField.objects.filter(is_system=True).exclude(key__in=("created_on", "last_seen_on")).delete()
    )
    if num_deleted:
        print(f"Deleted {num_deleted} unused system fields")

    # mark the remaining two date system fields as being proxy fields
    ContactField.objects.filter(is_system=True, key__in=("created_on", "last_seen_on")).update(is_proxy=True)


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [("contacts", "0188_contactfield_is_proxy_alter_contactfield_is_system")]

    operations = [migrations.RunPython(backfill_proxy_fields, reverse)]
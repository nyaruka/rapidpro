# Generated by Django 5.1.4 on 2025-04-08 14:28

from django.db import migrations


def migrate_bw_app_ids(apps, schema_editor):  # pragma: no cover
    Channel = apps.get_model("channels", "Channel")

    channels = Channel.objects.filter(channel_type="BW", is_active=True)
    num_updated = 0
    for channel in channels:
        app_id = channel.config.pop("application_id", None)
        if app_id:
            if channel.role == "SR":
                channel.config["messaging_application_id"] = app_id
            if channel.role == "CA":
                channel.config["voice_application_id"] = app_id

            channel.save(update_fields=("config",))
            num_updated += 1

    if num_updated:
        print(f"Updated {num_updated} BW channels")


class Migration(migrations.Migration):

    dependencies = [
        ("channels", "0194_populate_max_concurrent_calls"),
    ]

    operations = [
        migrations.RunPython(migrate_bw_app_ids, migrations.RunPython.noop),
    ]

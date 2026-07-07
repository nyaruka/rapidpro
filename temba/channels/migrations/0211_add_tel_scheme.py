from django.db import migrations


def add_tel_scheme(apps, schema_editor):
    Channel = apps.get_model("channels", "Channel")

    # channels which support the whatsapp scheme should now also support the tel scheme
    channels = Channel.objects.filter(schemes__contains=["whatsapp"]).exclude(schemes__contains=["tel"])

    num_updated = 0
    for channel in channels:
        channel.schemes = [*channel.schemes, "tel"]
        channel.save(update_fields=["schemes"])
        num_updated += 1

    if num_updated:
        print(f"Added tel scheme to {num_updated} channels")


def apply_manual():  # pragma: no cover
    from django.apps import apps

    add_tel_scheme(apps, None)


class Migration(migrations.Migration):
    dependencies = [
        ("channels", "0210_remove_channel_log_policy"),
    ]

    operations = [migrations.RunPython(add_tel_scheme, reverse_code=migrations.RunPython.noop)]

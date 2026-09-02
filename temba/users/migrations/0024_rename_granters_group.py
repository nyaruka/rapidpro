from django.db import migrations


def rename_granters_group(apps, schema_editor):  # pragma: no cover
    Group = apps.get_model("auth", "Group")

    Group.objects.filter(name="Granters").update(name="Global Administrators")


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("users", "0023_reset_dropped_languages"),
    ]

    operations = [migrations.RunPython(rename_granters_group, migrations.RunPython.noop)]

from django.db import migrations


def delete_dashboard_group(apps, schema_editor):  # pragma: no cover
    Group = apps.get_model("auth", "Group")

    Group.objects.filter(name="Dashboard").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("orgs", "0188_reset_dropped_languages"),
    ]

    operations = [migrations.RunPython(delete_dashboard_group, migrations.RunPython.noop)]

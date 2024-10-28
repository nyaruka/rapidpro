# Generated by Django 5.1.2 on 2024-10-24 16:34

from django.db import migrations


def backfill_default_teams(apps, schema_editor):  # pragma: no cover
    Org = apps.get_model("orgs", "Org")

    for org in Org.objects.filter(teams=None):
        org.teams.create(
            name="All Topics",
            is_default=True,
            is_system=True,
            all_topics=True,
            created_by=org.created_by,
            modified_by=org.modified_by,
        )


class Migration(migrations.Migration):

    dependencies = [("tickets", "0067_team_is_default")]

    operations = [migrations.RunPython(backfill_default_teams, migrations.RunPython.noop)]
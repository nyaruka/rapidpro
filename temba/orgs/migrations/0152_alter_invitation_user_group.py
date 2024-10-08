# Generated by Django 5.1 on 2024-10-07 21:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orgs", "0151_alter_usersettings_avatar"),
    ]

    operations = [
        migrations.AlterField(
            model_name="invitation",
            name="user_group",
            field=models.CharField(
                choices=[("A", "Administrator"), ("E", "Editor"), ("V", "Viewer"), ("T", "Agent")],
                default="E",
                max_length=1,
            ),
        ),
    ]

# Generated by Django 5.1.2 on 2024-11-28 19:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orgs", "0159_usersettings_is_system"),
    ]

    operations = [
        migrations.AlterField(
            model_name="itemcount",
            name="scope",
            field=models.CharField(max_length=128),
        ),
    ]
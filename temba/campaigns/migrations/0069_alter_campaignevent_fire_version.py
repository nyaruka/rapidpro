# Generated by Django 5.1.4 on 2025-03-04 23:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0068_add_version_to_event_fires"),
    ]

    operations = [
        migrations.AlterField(
            model_name="campaignevent",
            name="fire_version",
            field=models.IntegerField(default=0),
        ),
    ]

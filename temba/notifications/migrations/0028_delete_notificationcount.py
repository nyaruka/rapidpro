# Generated by Django 5.1.2 on 2024-11-05 19:48

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0027_update_triggers"),
    ]

    operations = [
        migrations.DeleteModel(
            name="NotificationCount",
        ),
    ]

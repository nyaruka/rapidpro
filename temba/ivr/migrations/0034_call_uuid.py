# Generated by Django 5.2.2 on 2025-06-20 14:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ivr", "0033_call_trigger"),
    ]

    operations = [
        migrations.AddField(
            model_name="call",
            name="uuid",
            field=models.UUIDField(null=True),
        ),
    ]

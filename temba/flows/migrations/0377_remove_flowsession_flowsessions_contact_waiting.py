# Generated by Django 5.1.4 on 2025-02-24 14:55

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("flows", "0376_flowrun_flowruns_by_session"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="flowsession",
            name="flowsessions_contact_waiting",
        ),
    ]

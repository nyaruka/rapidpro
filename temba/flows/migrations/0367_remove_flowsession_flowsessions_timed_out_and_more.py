# Generated by Django 5.1.4 on 2025-02-04 21:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flows", "0366_flowrun_session_uuid"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="flowsession",
            name="flowsessions_timed_out",
        ),
        migrations.RemoveIndex(
            model_name="flowsession",
            name="flows_session_waiting_expires",
        ),
        migrations.AlterField(
            model_name="flowsession",
            name="modified_on",
            field=models.DateTimeField(null=True),
        ),
        migrations.AlterField(
            model_name="flowsession",
            name="responded",
            field=models.BooleanField(null=True),
        ),
    ]

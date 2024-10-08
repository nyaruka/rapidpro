# Generated by Django 5.1 on 2024-09-25 16:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("msgs", "0274_alter_broadcast_created_by_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="broadcast",
            name="status",
            field=models.CharField(
                choices=[
                    ("P", "Pending"),
                    ("Q", "Queued"),
                    ("S", "Started"),
                    ("C", "Completed"),
                    ("F", "Failed"),
                    ("I", "Interrupted"),
                ],
                default="P",
                max_length=1,
            ),
        ),
    ]

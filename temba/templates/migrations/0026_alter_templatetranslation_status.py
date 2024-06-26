# Generated by Django 5.0.3 on 2024-04-04 18:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("templates", "0025_remove_templatetranslation_comps_as_dict"),
    ]

    operations = [
        migrations.AlterField(
            model_name="templatetranslation",
            name="status",
            field=models.CharField(
                choices=[("A", "Approved"), ("P", "Pending"), ("R", "Rejected"), ("X", "Unsupported")],
                default="P",
                max_length=1,
            ),
        ),
    ]

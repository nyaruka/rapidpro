# Generated by Django 4.2.8 on 2024-03-21 13:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("templates", "0023_remove_templatetranslation_content_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="templatetranslation",
            name="comps_as_dict",
            field=models.JSONField(null=True),
        ),
    ]
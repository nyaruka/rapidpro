# Generated by Django 4.2.8 on 2024-03-18 20:49

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("templates", "0021_alter_templatetranslation_components"),
    ]

    operations = [
        migrations.AlterField(
            model_name="templatetranslation",
            name="params",
            field=models.JSONField(null=True),
        ),
        migrations.AlterField(
            model_name="templatetranslation",
            name="variable_count",
            field=models.IntegerField(null=True),
        ),
    ]
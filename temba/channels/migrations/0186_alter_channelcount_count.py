# Generated by Django 5.1.2 on 2024-12-04 18:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("channels", "0185_alter_channel_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="channelcount",
            name="count",
            field=models.IntegerField(),
        ),
    ]
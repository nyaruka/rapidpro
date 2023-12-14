# Generated by Django 4.2.3 on 2023-12-11 15:24

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contacts", "0180_fix_bad_last_seen_on"),
    ]

    operations = [
        migrations.RunSQL("DROP INDEX contacts_contactgroupcount_unsquashed;"),
        migrations.AddIndex(
            model_name="contactgroupcount",
            index=models.Index(
                condition=models.Q(("is_squashed", False)), fields=["group"], name="contactgroupcounts_unsquashed"
            ),
        ),
    ]
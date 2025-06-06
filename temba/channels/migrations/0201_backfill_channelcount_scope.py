# Generated by Django 5.2.1 on 2025-06-03 22:17

from django.db import migrations, transaction

TYPE_TO_SCOPE = {
    "IM": "text:in",
    "IV": "voice:in",
    "OM": "text:out",
    "OV": "voice:out",
}


def backfill_channelcount_scope(apps, schema_editor):  # pragma: no cover
    ChannelCount = apps.get_model("channels", "ChannelCount")

    num_updated = 0
    while True:
        batch = list(ChannelCount.objects.filter(scope=None)[:1000])
        if not batch:
            break

        with transaction.atomic():
            for cc in batch:
                cc.scope = TYPE_TO_SCOPE[cc.count_type]
                cc.save(update_fields=("scope",))

        num_updated += len(batch)
        print(f"Updated {num_updated} channel counts with scope.")


class Migration(migrations.Migration):

    dependencies = [
        ("channels", "0200_channelcount_scope_alter_channelcount_day"),
    ]

    operations = [
        migrations.RunPython(backfill_channelcount_scope, migrations.RunPython.noop),
    ]

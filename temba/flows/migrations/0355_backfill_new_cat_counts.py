# Generated by Django 5.1.4 on 2025-01-09 18:35

import itertools

from django.db import migrations, transaction
from django.db.models import Sum


def backfill_new_counts(apps, schema_editor):  # pragma: no cover
    Flow = apps.get_model("flows", "Flow")

    flow_ids = list(Flow.objects.filter(is_active=True).order_by("id").values_list("id", flat=True))

    print(f"Updating result counts for {len(flow_ids)} flows...")

    num_backfilled = 0

    for id_batch in itertools.batched(flow_ids, 500):
        flows = Flow.objects.filter(id__in=id_batch).only("id").order_by("id")
        for flow in flows:
            backfill_for_flow(apps, flow)

        num_backfilled += len(flows)
        print(f"> updated counts for {num_backfilled} of {len(flow_ids)} flows")


def backfill_for_flow(apps, flow):  # pragma: no cover
    FlowResultCount = apps.get_model("flows", "FlowResultCount")

    to_create = []

    counts = flow.category_counts.values("result_key", "category_name").annotate(total=Sum("count"))
    for c in counts:
        if c["category_name"] and c["total"] > 0:
            to_create.append(
                FlowResultCount(
                    flow=flow, result=c["result_key"][:64], category=c["category_name"][:64], count=c["total"]
                )
            )

    with transaction.atomic():
        flow.result_counts.all().delete()
        FlowResultCount.objects.bulk_create(to_create)


class Migration(migrations.Migration):

    dependencies = [("flows", "0354_flowresultcount")]

    operations = [migrations.RunPython(backfill_new_counts, migrations.RunPython.noop)]

from packaging.version import Version

from django.db import migrations

# the schema compute_changes understands; older revisions used materially different
# definition shapes and aren't worth diffing here
MIN_SPEC = Version("13.0.0")


def backfill_flowrevision_changes(apps, schema_editor):  # pragma: no cover
    from temba.flows.changes import compute_changes

    FlowRevision = apps.get_model("flows", "FlowRevision")

    # iterate flows that still have any null-changes revision, paged by flow_id
    flow_ids_qs = (
        FlowRevision.objects.filter(changes__isnull=True)
        .values_list("flow_id", flat=True)
        .distinct()
        .order_by("flow_id")
    )

    last_flow_id = 0
    num_flows = 0
    num_updated = 0

    while True:
        flow_ids = list(flow_ids_qs.filter(flow_id__gt=last_flow_id)[:500])
        if not flow_ids:
            break

        for flow_id in flow_ids:
            prev_def = None
            updates = []

            # walk this flow's revisions in order; iterator keeps only one definition
            # in memory at a time (besides the prior definition we hold for diffing)
            qs = (
                FlowRevision.objects.filter(flow_id=flow_id)
                .order_by("revision", "id")
                .only("id", "definition", "spec_version", "changes")
            )

            for rev in qs.iterator(chunk_size=50):
                spec_ok = Version(rev.spec_version) >= MIN_SPEC

                if rev.changes is None and prev_def is not None and spec_ok:
                    rev.changes = compute_changes(prev_def, rev.definition)
                    updates.append(rev)

                    if len(updates) >= 200:
                        FlowRevision.objects.bulk_update(updates, ["changes"])
                        num_updated += len(updates)
                        updates = []

                # only carry forward a definition compute_changes can read; this also
                # ensures the first 13.x revision after a pre-13 history isn't diffed
                # against an incompatible prior shape
                prev_def = rev.definition if spec_ok else None

            if updates:
                FlowRevision.objects.bulk_update(updates, ["changes"])
                num_updated += len(updates)

            num_flows += 1
            last_flow_id = flow_id

        print(f"Processed {num_flows} flows, updated {num_updated} revisions")


def apply_manual():  # pragma: no cover
    from django.apps import apps

    backfill_flowrevision_changes(apps, None)


class Migration(migrations.Migration):
    dependencies = [
        ("flows", "0401_flowrevision_changes"),
    ]

    operations = [
        migrations.RunPython(backfill_flowrevision_changes, reverse_code=migrations.RunPython.noop),
    ]

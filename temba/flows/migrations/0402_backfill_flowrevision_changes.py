import logging

from packaging.version import InvalidVersion, Version

from django.db import migrations

logger = logging.getLogger(__name__)


def backfill_flowrevision_changes(apps, schema_editor):  # pragma: no cover
    from temba.flows.changes import compute_changes
    from temba.flows.models import Flow

    # the schema compute_changes understands; older revisions used materially different
    # definition shapes and aren't worth diffing here
    min_spec = Version(Flow.INITIAL_GOFLOW_VERSION)

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
            # load the whole flow's revisions; flows have bounded revision counts
            # (trim keeps recent + dailies), and a single bulk_update at the end
            # avoids interleaving writes with a server-side cursor
            revs = list(
                FlowRevision.objects.filter(flow_id=flow_id)
                .order_by("revision", "id")
                .only("id", "definition", "spec_version", "changes")
            )

            prev_def = None
            updates = []

            for rev in revs:
                try:
                    spec_ok = Version(rev.spec_version) >= min_spec
                except InvalidVersion:
                    spec_ok = False

                if spec_ok and prev_def is not None and not rev.changes:
                    try:
                        rev.changes = compute_changes(prev_def, rev.definition)
                    except Exception:
                        # malformed definition (e.g. nodes/actions missing uuid) — leave
                        # changes as null and keep going so one bad row doesn't block
                        # the rest of the backfill
                        logger.warning("could not compute changes for revision %d", rev.id, exc_info=True)
                    else:
                        updates.append(rev)

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
    atomic = False

    dependencies = [
        ("flows", "0401_flowrevision_changes"),
    ]

    operations = [
        migrations.RunPython(backfill_flowrevision_changes, reverse_code=migrations.RunPython.noop),
    ]

from django.db import migrations
from django.utils import timezone

from temba.utils.uuid import uuid4

SYSTEM_NAMES = {"shortcuts": "Shortcuts", "helpdesk": "Helpdesk"}


def backfill_system_knowledge(apps, schema_editor):  # pragma: no cover
    Org = apps.get_model("orgs", "Org")
    Knowledge = apps.get_model("knowledge", "Knowledge")

    # per type rather than per org so that an org caught halfway through a rolling deploy - one of its two system
    # rows already created by the new Org.initialize() - gets only the row it's missing
    for kb_type, base_name in SYSTEM_NAMES.items():
        num_created = 0

        while True:
            orgs = list(
                Org.objects.exclude(knowledge__knowledge_type=kb_type)
                .order_by("id")
                .values_list("id", "created_by_id", "modified_by_id")[:1000]
            )
            if not orgs:
                break

            for org_id, created_by_id, modified_by_id in orgs:
                # the org could already have something by this name - the other system row, or a user created
                # source - so find a free one
                name, count = base_name, 1
                while Knowledge.objects.filter(org_id=org_id, name__iexact=name).exists():
                    count += 1
                    name = f"{base_name} {count}"

                Knowledge.objects.create(
                    org_id=org_id,
                    uuid=uuid4(),
                    name=name,
                    knowledge_type=kb_type,
                    config={},
                    status="P",
                    error=None,
                    last_indexed_on=None,
                    is_system=True,
                    is_active=True,
                    num_items=0,
                    num_chunks=0,
                    created_by_id=created_by_id,
                    modified_by_id=modified_by_id,
                    created_on=timezone.now(),
                    modified_on=timezone.now(),
                )
                num_created += 1

            print(f"Created system {kb_type} knowledge for {num_created} orgs")


def apply_manual():  # pragma: no cover
    from django.apps import apps

    backfill_system_knowledge(apps, None)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("knowledge", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill_system_knowledge, migrations.RunPython.noop),
    ]

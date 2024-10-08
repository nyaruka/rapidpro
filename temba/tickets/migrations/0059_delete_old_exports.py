# Generated by Django 4.2.3 on 2024-03-05 20:03

from django.core.files.storage import default_storage
from django.db import migrations


def delete_old_exports(apps, schema_editor):  # pragma: no cover
    ExportTicketsTask = apps.get_model("tickets", "ExportTicketsTask")
    num_deleted = 0
    num_skipped = 0

    for task in ExportTicketsTask.objects.all():
        storage_path = f"orgs/{task.org_id}/ticket_exports/{task.uuid}.xlsx"

        try:
            default_storage.delete(storage_path)

            task.notifications.all().delete()
            task.delete()

            num_deleted += 1
        except Exception:
            print(f"Skipping deletion of old export {task.uuid} because stored file could not be deleted.")
            num_skipped += 1

    if num_deleted or num_skipped:
        print(f"Deleted {num_deleted} old exports and skipped {num_skipped} old exports.")


def reverse(apps, schema_editor):  # pragma: no cover
    pass


class Migration(migrations.Migration):
    dependencies = [("tickets", "0058_exportticketstask_item_count_and_more")]

    operations = [migrations.RunPython(delete_old_exports, reverse)]

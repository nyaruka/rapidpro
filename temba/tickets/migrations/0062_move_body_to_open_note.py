# Generated by Django 5.0.8 on 2024-08-08 14:58

from django.db import migrations


def move_body_to_open_note(apps, schema_editor):  # pragma: no cover
    Ticket = apps.get_model("tickets", "Ticket")

    num_updated = 0

    for ticket in Ticket.objects.exclude(body=None).exclude(body=""):
        ticket.events.filter(event_type="O").update(note=ticket.body)

        num_updated += 1

        if num_updated % 1000 == 0:  # pragma: no cover
            print(f" > updated {num_updated} tickets")

    if num_updated:
        print(f" > Updated {num_updated} tickets")


class Migration(migrations.Migration):

    dependencies = [("tickets", "0061_alter_ticket_body_alter_ticketevent_note")]

    operations = [migrations.RunPython(move_body_to_open_note, migrations.RunPython.noop)]

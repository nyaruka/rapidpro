import os

import requests

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Sum

from temba.contacts.models import ContactGroup, ContactGroupCount


class Command(BaseCommand):  # pragma: no cover
    help = "Checks group counts are the same between the number of contacts and the squashable count in the DB"

    def handle(self, *args, **options):
        print("Checking group counts...")
        groups = ContactGroup.all_groups.all()

        counts = ContactGroupCount.objects.filter(group__in=groups)
        counts = counts.values("group").order_by("group").annotate(count_sum=Sum("count"))
        counts_by_group_id = {c["group"]: c["count_sum"] for c in counts}

        wrong_counts_groups = []

        for group in groups:
            db_contacts = group.contacts.filter(is_active=True)
            group_counts = counts_by_group_id.get(group.id, 0)
            
            contacts_count = db_contacts.count()
            
            if contacts_count != group_counts:
                wrong_counts_groups.append(group.id)
                print(f"Group: {group.id},  Contacts count: {db_contacts.count()}, DB Count: {group_counts}")

        
        if wrong_counts_groups:
            print("=" * 80)
            print(f"Wrong group counts in: {wrong_counts_groups}")
            print("=" * 80)
        else:
            print("All group checked")
        print("Done!")
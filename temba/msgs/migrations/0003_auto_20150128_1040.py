# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

def remove_comma_in_labels_name(apps, schema_editor):
    Label = apps.get_model('msgs', 'Label')
    for label in Label.objects.filter(name__icontains=','):
        label.name = label.name.replace(', ', ' ').replace(',', ' ')
        label.save()

class Migration(migrations.Migration):

    dependencies = [
        ('msgs', '0002_broadcast_channel'),
    ]

    operations = [
        migrations.RunPython(remove_comma_in_labels_name),
    ]

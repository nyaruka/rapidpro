# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0005_auto_20150416_0729'),
        ('flows', '0026_auto_20150805_0504'),
    ]

    operations = [
        migrations.AddField(
            model_name='flowrun',
            name='org',
            field=models.ForeignKey(related_name='runs', to='orgs.Org', null=True),
            preserve_default=True,
        ),
    ]

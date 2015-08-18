# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

class Migration(migrations.Migration):

    dependencies = [
        ('flows', '0028_populate_flowrun_orgs'),
    ]

    operations = [
        migrations.AlterField(
            model_name='flowrun',
            name='org',
            field=models.ForeignKey(related_name='runs', to='orgs.Org'),
            preserve_default=True,
        ),
    ]

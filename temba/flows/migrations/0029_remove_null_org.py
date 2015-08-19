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
        migrations.AddField(
            model_name='flowrun',
            name='modified_on',
            field=models.DateTimeField(help_text='When this flow run was last updated', auto_now=True, null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='flowrun',
            name='org',
            field=models.ForeignKey(related_name='runs', to='orgs.Org', db_index=False),
            preserve_default=True,
        ),
    ]

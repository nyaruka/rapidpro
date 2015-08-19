# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flows', '0032_auto_20150819_1531'),
    ]

    operations = [
        migrations.AlterField(
            model_name='flowrun',
            name='expired_on',
            field=models.DateTimeField(help_text='When this flow run expired', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='flowrun',
            name='expires_on',
            field=models.DateTimeField(help_text='When this flow run will expire', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='flowrun',
            name='flow',
            field=models.ForeignKey(related_name='runs', to='flows.Flow', db_index=False),
            preserve_default=True,
        ),
    ]

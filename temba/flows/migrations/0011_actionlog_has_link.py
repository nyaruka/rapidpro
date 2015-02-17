# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flows', '0010_auto_20150210_1845'),
    ]

    operations = [
        migrations.AddField(
            model_name='actionlog',
            name='has_link',
            field=models.BooleanField(default=False, help_text='If this has a clickable link'),
            preserve_default=True,
        ),
    ]

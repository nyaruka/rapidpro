# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    # language=SQL
    CREATE_SQL = """
    CREATE INDEX flows_flowrun_org_id_modified_on ON flows_flowrun(org_id, modified_on desc);
    CREATE INDEX flows_flowrun_flow_id_modified_on ON flows_flowrun(flow_id, modified_on desc);
    """

    # language=SQL
    DROP_SQL = """
    DROP INDEX IF EXISTS flows_flowrun_org_id_modified_on;
    DROP INDEX IF EXISTS flows_flowrun_flow_id_modified_on;
    """

    dependencies = [
        ('flows', '0030_populate_modified_on'),
    ]

    operations = [
        migrations.RunSQL(CREATE_SQL, DROP_SQL),
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

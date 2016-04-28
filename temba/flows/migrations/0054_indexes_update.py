# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


INDEX_SQL = """
DROP INDEX IF EXISTS flows_flowrun_org_id_modified_on;
DROP INDEX IF EXISTS flows_flowrun_org_id_modified_on_responded;
DROP INDEX IF EXISTS flows_flowrun_flow_id_modified_on;
DROP INDEX IF EXISTS flows_flowrun_flow_id_modified_on_responded;

CREATE INDEX flows_flowrun_org_id_modified_on
ON flows_flowrun (org_id, modified_on DESC, id DESC);

CREATE INDEX flows_flowrun_org_id_modified_on_responded
ON flows_flowrun (org_id, modified_on DESC, id DESC)
WHERE responded = TRUE;

CREATE INDEX flows_flowrun_flow_id_modified_on
ON flows_flowrun (flow_id, modified_on DESC, id DESC);

CREATE INDEX flows_flowrun_flow_id_modified_on_responded
ON flows_flowrun (flow_id, modified_on DESC, id DESC)
WHERE responded = TRUE;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('flows', '0053_auto_20160414_0642'),
    ]

    operations = [
        migrations.RunSQL(INDEX_SQL)
    ]

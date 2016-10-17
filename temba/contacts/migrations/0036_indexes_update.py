# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


INDEX_SQL = """
DROP INDEX IF EXISTS contacts_contact_org_id_modified_on_active;
DROP INDEX IF EXISTS contacts_contact_org_id_modified_on_inactive;

CREATE INDEX contacts_contact_org_id_modified_on_active
ON contacts_contact (org_id, modified_on DESC, id DESC)
WHERE is_test = false AND is_active = true;

CREATE INDEX contacts_contact_org_id_modified_on_inactive
ON contacts_contact (org_id, modified_on DESC, id DESC)
WHERE is_test = false AND is_active = false;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0035_auto_20160414_0642'),
    ]

    operations = [
        migrations.RunSQL(INDEX_SQL)
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


INDEX_SQL = """
DROP INDEX IF EXISTS msg_visibility_direction_type_created_inbound;
DROP INDEX IF EXISTS msg_direction_modified_inbound;
DROP INDEX IF EXISTS msgs_msg_outbox_label;
DROP INDEX IF EXISTS msgs_msg_sent_label;
DROP INDEX IF EXISTS msgs_msg_failed_label;

CREATE INDEX msgs_broadcasts_org_id_created_on_active
ON msgs_broadcast(org_id, created_on DESC, id DESC)
WHERE is_active = true;

CREATE INDEX msg_visibility_direction_type_created_inbound
ON msgs_msg(org_id, visibility, direction, msg_type, created_on DESC, id DESC)
WHERE direction = 'I';

CREATE INDEX msg_direction_modified_inbound
ON msgs_msg (org_id, direction, modified_on DESC, id DESC)
WHERE direction = 'I';

CREATE INDEX msgs_msg_outbox_label
ON msgs_msg(org_id, created_on DESC, id DESC)
WHERE direction = 'O' AND visibility = 'V' AND status IN ('P', 'Q');

CREATE INDEX msgs_msg_sent_label
ON msgs_msg(org_id, created_on DESC, id DESC)
WHERE direction = 'O' AND visibility = 'V' AND status IN ('W', 'S', 'D');

CREATE INDEX msgs_msg_failed_label
ON msgs_msg(org_id, created_on DESC, id DESC)
WHERE direction = 'O' AND visibility = 'V' AND status = 'F';
"""


class Migration(migrations.Migration):

    dependencies = [
        ('msgs', '0057_update_triggers'),
    ]

    operations = [
        migrations.RunSQL(INDEX_SQL)
    ]

# Generated by Django 5.0.4 on 2024-04-25 14:43

from django.conf import settings
from django.db import migrations, models

# language=SQL
TRIGGER_SQL = """
----------------------------------------------------------------------
-- Determines the (mutually exclusive) system label for a msg record
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION temba_msg_determine_system_label(_msg msgs_msg) RETURNS CHAR(1) STABLE AS $$
BEGIN
  IF _msg.direction = 'I' THEN
    -- incoming IVR messages aren't part of any system labels
    IF _msg.msg_type = 'V' THEN
      RETURN NULL;
    END IF;

    IF _msg.visibility = 'V' AND _msg.status = 'H' AND _msg.flow_id IS NULL THEN
      RETURN 'I';
    ELSIF _msg.visibility = 'V' AND _msg.status = 'H' AND _msg.flow_id IS NOT NULL THEN
      RETURN 'W';
    ELSIF _msg.visibility = 'A'  AND _msg.status = 'H' THEN
      RETURN 'A';
    END IF;
  ELSE
    IF _msg.VISIBILITY = 'V' THEN
      IF _msg.status = 'I' OR _msg.status = 'Q' OR _msg.status = 'E' THEN
        RETURN 'O';
      ELSIF _msg.status = 'W' OR _msg.status = 'S' OR _msg.status = 'D' OR _msg.status = 'R' THEN
        RETURN 'S';
      ELSIF _msg.status = 'F' THEN
        RETURN 'X';
      END IF;
    END IF;
  END IF;

  RETURN NULL; -- might not match any label
END;
$$ LANGUAGE plpgsql;

"""


class Migration(migrations.Migration):

    dependencies = [
        ("channels", "0185_alter_channel_name"),
        ("contacts", "0187_delete_exportcontactstask"),
        ("flows", "0334_remove_flowrun_submitted_by"),
        ("msgs", "0261_msg_templating"),
        ("orgs", "0142_alter_usersettings_user"),
        ("tickets", "0060_delete_exportticketstask"),
        ("sql", "0006_squashed"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="msg",
            name="no_sent_status_without_sent_on",
        ),
        migrations.RemoveIndex(
            model_name="msg",
            name="msgs_sent",
        ),
        migrations.AlterField(
            model_name="msg",
            name="status",
            field=models.CharField(
                choices=[
                    ("P", "Pending"),
                    ("H", "Handled"),
                    ("I", "Initializing"),
                    ("Q", "Queued"),
                    ("W", "Wired"),
                    ("S", "Sent"),
                    ("D", "Delivered"),
                    ("R", "Read"),
                    ("E", "Error"),
                    ("F", "Failed"),
                ],
                db_index=True,
                default="P",
                max_length=1,
            ),
        ),
        migrations.AddIndex(
            model_name="msg",
            index=models.Index(
                condition=models.Q(("direction", "O"), ("status__in", ("W", "S", "D", "R")), ("visibility", "V")),
                fields=["org", "-sent_on", "-id"],
                name="msgs_sent",
            ),
        ),
        migrations.AddConstraint(
            model_name="msg",
            constraint=models.CheckConstraint(
                check=models.Q(("sent_on__isnull", True), ("status__in", ("W", "S", "D", "R")), _negated=True),
                name="no_sent_status_without_sent_on",
            ),
        ),
        migrations.RunSQL(TRIGGER_SQL, ""),
    ]

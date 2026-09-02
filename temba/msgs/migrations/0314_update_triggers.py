from django.db import migrations

# now that Msg.folder is maintained by mailroom and courier on every write, backfilled for everything that predates
# that, and read by every folder view, the folder counts derive from it too rather than re-deriving the folder from
# direction/visibility/status/flow. That makes the counts agree with the folder views by construction: a message is
# counted in exactly the folder it's listed in. It also means a write which changes a message's state without
# updating its folder moves no counts - which is the right outcome, as it also wouldn't move the message between
# folders.
SQL = """
----------------------------------------------------------------------
-- Determines the item count scope for a msg record
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION temba_msg_countscope(_msg msgs_msg) RETURNS TEXT STABLE AS $$
BEGIN
  IF _msg.folder IN ('I', 'W', 'A', 'O', 'S', 'X') THEN
    RETURN 'msgs:folder:' || _msg.folder;
  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""

# the previous definition, deriving the folder from the message's state, so that this can be unapplied
REVERSE_SQL = """
CREATE OR REPLACE FUNCTION temba_msg_countscope(_msg msgs_msg) RETURNS TEXT STABLE AS $$
BEGIN
  IF _msg.direction = 'I' THEN
    IF _msg.visibility = 'V' AND _msg.status = 'H' AND _msg.flow_id IS NULL THEN
      RETURN 'msgs:folder:I';
    ELSIF _msg.visibility = 'V' AND _msg.status = 'H' AND _msg.flow_id IS NOT NULL THEN
      RETURN 'msgs:folder:W';
    ELSIF _msg.visibility = 'A'  AND _msg.status = 'H' THEN
      RETURN 'msgs:folder:A';
    END IF;
  ELSE
    IF _msg.VISIBILITY = 'V' THEN
      IF _msg.status = 'I' OR _msg.status = 'Q' OR _msg.status = 'E' THEN
        RETURN 'msgs:folder:O';
      ELSIF _msg.status = 'W' OR _msg.status = 'S' OR _msg.status = 'D' OR _msg.status = 'R' THEN
        RETURN 'msgs:folder:S';
      ELSIF _msg.status = 'F' THEN
        RETURN 'msgs:folder:X';
      END IF;
    END IF;
  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("msgs", "0313_alter_msg_folder"),
    ]

    operations = [
        migrations.RunSQL(SQL, REVERSE_SQL),
    ]

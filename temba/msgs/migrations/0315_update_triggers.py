from django.db import migrations

# the label counts (which are split by whether the message is archived or deleted) and the guard against archiving
# outgoing messages are keyed on the folder rather than visibility, like the folder counts already are. That's the last
# thing in the database that read visibility to tell whether a message is archived, so archived can stop being a
# visibility - and when the visibility of messages archived before then is updated, no counts move.
SQL = """
----------------------------------------------------------------------
-- Handles DELETE statements on msgs_msg_labels table
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION temba_msg_labels_on_delete() RETURNS TRIGGER AS $$
BEGIN
    -- add negative label count for all deleted rows
    INSERT INTO msgs_labelcount("label_id", "is_archived", "count", "is_squashed")
    SELECT o.label_id, m.folder IN ('A', 'D'), -count(*), FALSE FROM oldtab o
    INNER JOIN msgs_msg m ON m.id = o.msg_id
    GROUP BY o.label_id, m.folder IN ('A', 'D');

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

----------------------------------------------------------------------
-- Handles INSERT statements on msgs_msg_labels table
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION temba_msg_labels_on_insert() RETURNS TRIGGER AS $$
BEGIN
    -- add label count for all new rows
    INSERT INTO msgs_labelcount("label_id", "is_archived", "count", "is_squashed")
    SELECT n.label_id, m.folder IN ('A', 'D'), count(*), FALSE FROM newtab n
    INNER JOIN msgs_msg m ON m.id = n.msg_id
    GROUP BY n.label_id, m.folder IN ('A', 'D');

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

----------------------------------------------------------------------
-- Trigger procedure to update user and system labels on column changes
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION temba_msg_on_change() RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP IN ('INSERT', 'UPDATE') THEN
    -- prevent illegal message states
    IF NEW.direction = 'I' AND NEW.status NOT IN ('P', 'H') THEN
      RAISE EXCEPTION 'Incoming messages can only be PENDING or HANDLED';
    END IF;
    IF NEW.direction = 'O' AND NEW.folder = 'A' THEN
      RAISE EXCEPTION 'Outgoing messages cannot be archived';
    END IF;
  END IF;

  -- existing message updated
  IF TG_OP = 'UPDATE' THEN
    -- restrict changes
    IF NEW.direction <> OLD.direction THEN RAISE EXCEPTION 'Cannot change direction on messages'; END IF;
    IF NEW.created_on <> OLD.created_on THEN RAISE EXCEPTION 'Cannot change created_on on messages'; END IF;
    IF NEW.msg_type <> OLD.msg_type THEN RAISE EXCEPTION 'Cannot change msg_type on messages'; END IF;
  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

----------------------------------------------------------------------
-- Handles UPDATE statements on msg table
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION temba_msg_on_update() RETURNS TRIGGER AS $$
BEGIN
    -- add negative item counts for all rows that belonged to a folder they no longer belong to
    INSERT INTO orgs_itemcount("org_id", "scope", "count", "is_squashed")
    SELECT o.org_id, temba_msg_countscope(o), -count(*), FALSE FROM oldtab o
    INNER JOIN newtab n ON n.id = o.id
    WHERE temba_msg_countscope(o) IS DISTINCT FROM temba_msg_countscope(n) AND temba_msg_countscope(o) IS NOT NULL
    GROUP BY 1, 2;

    -- add positive item counts for all rows that now belong to a folder they didn't belong to
    INSERT INTO orgs_itemcount("org_id", "scope", "count", "is_squashed")
    SELECT n.org_id, temba_msg_countscope(n), count(*), FALSE FROM newtab n
    INNER JOIN oldtab o ON o.id = n.id
    WHERE temba_msg_countscope(o) IS DISTINCT FROM temba_msg_countscope(n) AND temba_msg_countscope(n) IS NOT NULL
    GROUP BY 1, 2;

    -- add negative old-state label counts for all messages being archived/restored
    INSERT INTO msgs_labelcount("label_id", "is_archived", "count", "is_squashed")
    SELECT ml.label_id, o.folder IN ('A', 'D'), -count(*), FALSE FROM oldtab o
    INNER JOIN newtab n ON n.id = o.id
    INNER JOIN msgs_msg_labels ml ON ml.msg_id = o.id
    WHERE (o.folder IN ('A', 'D')) <> (n.folder IN ('A', 'D'))
    GROUP BY 1, 2;

    -- add new-state label counts for all messages being archived/restored
    INSERT INTO msgs_labelcount("label_id", "is_archived", "count", "is_squashed")
    SELECT ml.label_id, n.folder IN ('A', 'D'), count(*), FALSE FROM newtab n
    INNER JOIN oldtab o ON o.id = n.id
    INNER JOIN msgs_msg_labels ml ON ml.msg_id = n.id
    WHERE (o.folder IN ('A', 'D')) <> (n.folder IN ('A', 'D'))
    GROUP BY 1, 2;

    -- add new flow activity counts for incoming messages now marked as handled by a flow
    INSERT INTO flows_flowactivitycount("flow_id", "scope", "count", "is_squashed")
    SELECT s.flow_id, unnest(ARRAY[
            format('msgsin:hour:%s', extract(hour FROM NOW())),
            format('msgsin:dow:%s', extract(isodow FROM NOW())),
            format('msgsin:date:%s', NOW()::date)
        ]), s.msgs, FALSE
    FROM (
        SELECT n.flow_id, count(*) AS msgs FROM newtab n INNER JOIN oldtab o ON o.id = n.id
        WHERE n.direction = 'I' AND o.flow_id IS NULL AND n.flow_id IS NOT NULL
        GROUP BY 1
    ) s;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""

# the previous definitions, keyed on visibility, so that this can be unapplied
REVERSE_SQL = """
----------------------------------------------------------------------
-- Handles DELETE statements on msgs_msg_labels table
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION temba_msg_labels_on_delete() RETURNS TRIGGER AS $$
BEGIN
    -- add negative label count for all deleted rows
    INSERT INTO msgs_labelcount("label_id", "is_archived", "count", "is_squashed")
    SELECT o.label_id, m.visibility != 'V', -count(*), FALSE FROM oldtab o
    INNER JOIN msgs_msg m ON m.id = o.msg_id
    GROUP BY o.label_id, m.visibility != 'V';

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

----------------------------------------------------------------------
-- Handles INSERT statements on msgs_msg_labels table
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION temba_msg_labels_on_insert() RETURNS TRIGGER AS $$
BEGIN
    -- add label count for all new rows
    INSERT INTO msgs_labelcount("label_id", "is_archived", "count", "is_squashed")
    SELECT n.label_id, m.visibility != 'V', count(*), FALSE FROM newtab n
    INNER JOIN msgs_msg m ON m.id = n.msg_id
    GROUP BY n.label_id, m.visibility != 'V';

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

----------------------------------------------------------------------
-- Trigger procedure to update user and system labels on column changes
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION temba_msg_on_change() RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP IN ('INSERT', 'UPDATE') THEN
    -- prevent illegal message states
    IF NEW.direction = 'I' AND NEW.status NOT IN ('P', 'H') THEN
      RAISE EXCEPTION 'Incoming messages can only be PENDING or HANDLED';
    END IF;
    IF NEW.direction = 'O' AND NEW.visibility = 'A' THEN
      RAISE EXCEPTION 'Outgoing messages cannot be archived';
    END IF;
  END IF;

  -- existing message updated
  IF TG_OP = 'UPDATE' THEN
    -- restrict changes
    IF NEW.direction <> OLD.direction THEN RAISE EXCEPTION 'Cannot change direction on messages'; END IF;
    IF NEW.created_on <> OLD.created_on THEN RAISE EXCEPTION 'Cannot change created_on on messages'; END IF;
    IF NEW.msg_type <> OLD.msg_type THEN RAISE EXCEPTION 'Cannot change msg_type on messages'; END IF;
  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

----------------------------------------------------------------------
-- Handles UPDATE statements on msg table
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION temba_msg_on_update() RETURNS TRIGGER AS $$
BEGIN
    -- add negative item counts for all rows that belonged to a folder they no longer belong to
    INSERT INTO orgs_itemcount("org_id", "scope", "count", "is_squashed")
    SELECT o.org_id, temba_msg_countscope(o), -count(*), FALSE FROM oldtab o
    INNER JOIN newtab n ON n.id = o.id
    WHERE temba_msg_countscope(o) IS DISTINCT FROM temba_msg_countscope(n) AND temba_msg_countscope(o) IS NOT NULL
    GROUP BY 1, 2;

    -- add positive item counts for all rows that now belong to a folder they didn't belong to
    INSERT INTO orgs_itemcount("org_id", "scope", "count", "is_squashed")
    SELECT n.org_id, temba_msg_countscope(n), count(*), FALSE FROM newtab n
    INNER JOIN oldtab o ON o.id = n.id
    WHERE temba_msg_countscope(o) IS DISTINCT FROM temba_msg_countscope(n) AND temba_msg_countscope(n) IS NOT NULL
    GROUP BY 1, 2;

    -- add negative old-state label counts for all messages being archived/restored
    INSERT INTO msgs_labelcount("label_id", "is_archived", "count", "is_squashed")
    SELECT ml.label_id, o.visibility != 'V', -count(*), FALSE FROM oldtab o
    INNER JOIN newtab n ON n.id = o.id
    INNER JOIN msgs_msg_labels ml ON ml.msg_id = o.id
    WHERE (o.visibility = 'V' AND n.visibility != 'V') or (o.visibility != 'V' AND n.visibility = 'V')
    GROUP BY 1, 2;

    -- add new-state label counts for all messages being archived/restored
    INSERT INTO msgs_labelcount("label_id", "is_archived", "count", "is_squashed")
    SELECT ml.label_id, n.visibility != 'V', count(*), FALSE FROM newtab n
    INNER JOIN oldtab o ON o.id = n.id
    INNER JOIN msgs_msg_labels ml ON ml.msg_id = n.id
    WHERE (o.visibility = 'V' AND n.visibility != 'V') or (o.visibility != 'V' AND n.visibility = 'V')
    GROUP BY 1, 2;

    -- add new flow activity counts for incoming messages now marked as handled by a flow
    INSERT INTO flows_flowactivitycount("flow_id", "scope", "count", "is_squashed")
    SELECT s.flow_id, unnest(ARRAY[
            format('msgsin:hour:%s', extract(hour FROM NOW())),
            format('msgsin:dow:%s', extract(isodow FROM NOW())),
            format('msgsin:date:%s', NOW()::date)
        ]), s.msgs, FALSE
    FROM (
        SELECT n.flow_id, count(*) AS msgs FROM newtab n INNER JOIN oldtab o ON o.id = n.id
        WHERE n.direction = 'I' AND o.flow_id IS NULL AND n.flow_id IS NOT NULL
        GROUP BY 1
    ) s;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("msgs", "0314_update_triggers"),
    ]

    operations = [
        migrations.RunSQL(SQL, REVERSE_SQL),
    ]

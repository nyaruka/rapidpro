from django.db import migrations

SQL = """
DROP FUNCTION IF EXISTS contact_toggle_system_group(INT, INT, CHAR(1), BOOLEAN);

----------------------------------------------------------------------
-- Convenience method to call contact_toggle_system_group with a row
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION
  contact_toggle_system_group(_contact contacts_contact, _group_type CHAR(1), _add BOOLEAN)
RETURNS VOID AS $$
DECLARE
  _group_id BIGINT;
BEGIN
  PERFORM contact_toggle_system_group(_contact.id, _contact.org_id, _group_type, _add);
END;
$$ LANGUAGE plpgsql;

----------------------------------------------------------------------
-- Toggle a contact's membership of a system group in their org
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION
  contact_toggle_system_group(_contact_id BIGINT, _org_id BIGINT, _group_type CHAR(1), _add BOOLEAN)
RETURNS VOID AS $$
DECLARE
  _group_id BIGINT;
BEGIN
  -- lookup the group id
  SELECT id INTO STRICT _group_id FROM contacts_contactgroup
  WHERE org_id = _org_id AND group_type = _group_type;

  -- don't do anything if group doesn't exist for some inexplicable reason
  IF _group_id IS NULL THEN
    RETURN;
  END IF;

  IF _add THEN
    BEGIN
      INSERT INTO contacts_contactgroup_contacts (contactgroup_id, contact_id) VALUES (_group_id, _contact_id);
    EXCEPTION WHEN unique_violation THEN
      -- do nothing
    END;
  ELSE
    DELETE FROM contacts_contactgroup_contacts WHERE contactgroup_id = _group_id AND contact_id = _contact_id;
  END IF;
END;
$$ LANGUAGE plpgsql;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("contacts", "0217_alter_contactfield_id_alter_contactgroup_id_and_more"),
        ("sql", "0008_squashed"),
    ]

    operations = [migrations.RunSQL(SQL, reverse_sql=migrations.RunSQL.noop)]


CREATE SCHEMA IF NOT EXISTS es_update_contact;

CREATE TABLE IF NOT EXISTS es_update_contact.task (
  id BIGSERIAL PRIMARY KEY,
  contact_pk INTEGER NOT NULL,
  contact_document TEXT NOT NULL,
  created_on TIMESTAMP DEFAULT now()
);


CREATE OR REPLACE FUNCTION es_update_contact.serialize_contact(i_org_id INTEGER, i_contact_id INTEGER)

  RETURNS text AS

$BODY$
  DECLARE
    v_query TEXT;
    v_field RECORD;

    q_fields text[];
    q_cte_list text[];
    q_field_values text[];
    q_field_predicates text[];

    t_query text;
    t_result text;
  BEGIN

    v_query := format($query$
    select row_to_json(row)::text FROM (

with contact_urn AS (
  select contact.id as contact_id, array_agg(cu.identity ORDER BY priority DESC, cu.id) as urns
  FROM contacts_contact AS contact LEFT JOIN contacts_contacturn cu ON contact.id = cu.contact_id
    where contact.id = %L
  group by contact.id
),
  contact_groups AS (
    select contact.id as contact_id, array_agg(cg.name ORDER BY cg.id) as groups
    FROM contacts_contact contact left join contacts_contactgroup_contacts ccc ON contact.id = ccc.contact_id
  INNER JOIN contacts_contactgroup cg ON ccc.contactgroup_id = cg.id
      where contact.id = %L AND ccc.contact_id = %L
    GROUP BY contact.id
  ), $query$, i_contact_id, i_contact_id, i_contact_id);

    -- read contact field definition for specified org
    t_query := format($$SELECT id, key, value_type FROM public.contacts_contactfield WHERE org_id = %L AND is_active = TRUE ORDER BY id$$, i_org_id);

    FOR v_field in execute t_query LOOP

      q_fields := array_append(q_fields, format($$%I$$, v_field.key));
      q_field_values := array_append(q_field_values, format($$%L, %I.value$$, v_field.key, v_field.key));
      q_field_predicates := array_append(q_field_predicates, format($$%I ON contact.id = %I.contact_id$$, v_field.key, v_field.key));


      IF v_field.value_type = 'T' THEN
        q_cte_list := array_append(q_cte_list, format(
          $$%I AS (
          select contact_id, string_value as value
          from public.values_value
          WHERE org_id = %L AND contact_field_id = %L AND contact_id = %L
          ORDER BY 1,2)$$, v_field.key, i_org_id, v_field.id, i_contact_id
        ));
      ELSEIF v_field.value_type = 'N' THEN
        q_cte_list := array_append(q_cte_list, format(
          $$%I AS (
          select contact_id, decimal_value as value
          from public.values_value
          WHERE org_id = %L AND contact_field_id = %L AND contact_id = %L
          ORDER BY 1,2)$$, v_field.key, i_org_id, v_field.id, i_contact_id
        ));
        ELSEIF v_field.value_type = 'D' THEN
        q_cte_list := array_append(q_cte_list, format(
          $$%I AS (
          select contact_id, datetime_value as value
          from public.values_value
          WHERE org_id = %L AND contact_field_id = %L AND contact_id = %L
          ORDER BY 1,2)$$, v_field.key, i_org_id, v_field.id, i_contact_id
        ));
        ELSEIF v_field.value_type = any('{W, I, S}') THEN
        q_cte_list := array_append(q_cte_list, format(
          $$%I AS (
          select contact_id, path as value
          from public.values_value JOIN locations_adminboundary on values_value.location_value_id = locations_adminboundary.id
          WHERE org_id = %L AND contact_field_id = %L AND contact_id = %L
          ORDER BY 1,2)$$, v_field.key, i_org_id, v_field.id, i_contact_id
        ));
      END IF;
    END LOOP;

    v_query := v_query || array_to_string(q_cte_list, ', ');

    v_query := v_query || format($$
    select
            contact.id as id,
            contact.name as name,
            contact.language as language,
            contact.is_blocked as is_blocked,
            contact.is_stopped as is_stopped,
            contact.is_test as is_test,
            contact.is_active as is_active,
            contact_urn.urns,
            contact_groups.groups,
            jsonb_build_object(
                %s
            ) as fields
$$, array_to_string(q_field_values, ', '));


    v_query := v_query || format($$
FROM contacts_contact as contact LEFT JOIN contact_urn ON contact.id = contact_urn.contact_id LEFT JOIN contact_groups ON contact.id = contact_groups.contact_id LEFT JOIN %s
WHERE contact.id = %L
ORDER BY id) as row$$, array_to_string(q_field_predicates, ' LEFT JOIN '), i_contact_id);


    -- RAISE NOTICE '%', v_query;
    EXECUTE v_query INTO t_result;

    return t_result;

  END;
  $BODY$
  LANGUAGE plpgsql STABLE;


CREATE OR REPLACE FUNCTION es_update_contact.enqueue_contact()

  RETURNS TRIGGER AS

$BODY$
  DECLARE
  BEGIN

    INSERT INTO es_update_contact.task (contact_pk, contact_document) SELECT NEW.id, es_update_contact.serialize_contact(NEW.org_id, NEW.id);

    RETURN NEW;

  END;
  $BODY$
  LANGUAGE plpgsql VOLATILE ;


CREATE OR REPLACE FUNCTION es_update_contact.dequeue_contact()

  RETURNS es_update_contact.task AS

$BODY$
  DECLARE
    v_task es_update_contact.task;
  BEGIN

    DELETE FROM es_update_contact.task
    WHERE id = (
      SELECT id FROM es_update_contact.task
      ORDER BY id
      FOR UPDATE SKIP LOCKED
      LIMIT 1
    )
    RETURNING * INTO v_task;

    RETURN v_task;
  END;
$BODY$
LANGUAGE plpgsql VOLATILE;


CREATE TRIGGER sync_es_contact AFTER INSERT OR UPDATE ON public.contacts_contact
  FOR EACH ROW EXECUTE PROCEDURE es_update_contact.enqueue_contact();


-- DROP TRIGGER sync_es_contact ON public.contacts_contact;

-- select * from es_update_contact.serialize_contact(1, 43);
-- select * from es_update_contact.enqueue_contact(1, 40);

-- select * from es_update_contact.dequeue_contact();


-- DO $BODY$
-- DECLARE
--   v_id integer;
-- BEGIN
-- FOR v_id IN 1..10000 LOOP
--   update contacts_contact set name = '123' where id=v_id;
-- END LOOP;
-- END;
-- $BODY$;
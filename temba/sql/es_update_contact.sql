
CREATE SCHEMA IF NOT EXISTS es_update_contact;

CREATE TABLE IF NOT EXISTS es_update_contact.task (
  contact_pk INTEGER NOT NULL,
  contact_org_id INTEGER NOT NULL,
  created_on TIMESTAMP DEFAULT now(),
  PRIMARY KEY (contact_pk, contact_org_id)
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


CREATE OR REPLACE FUNCTION es_update_contact.enqueue_contact(i_org_id INTEGER, i_contact_id INTEGER)
RETURNS SETOF es_update_contact.task AS

$BODY$
  DECLARE
  BEGIN

    -- on duplicate work item, do nothing
    RETURN QUERY INSERT INTO es_update_contact.task (contact_pk, contact_org_id) VALUES (i_contact_id, i_org_id) ON CONFLICT DO NOTHING
      RETURNING *;

  END;
  $BODY$
  LANGUAGE plpgsql VOLATILE ;


CREATE OR REPLACE FUNCTION es_update_contact.dequeue_contact(i_max_tasks INTEGER DEFAULT 1000)

  RETURNS SETOF es_update_contact.task AS

$BODY$
  BEGIN

    RETURN QUERY DELETE FROM es_update_contact.task
    WHERE contact_pk IN (
      SELECT contact_pk FROM es_update_contact.task
      ORDER BY created_on
      FOR UPDATE SKIP LOCKED
      LIMIT i_max_tasks
    )
    RETURNING *;
  END;
$BODY$
LANGUAGE plpgsql VOLATILE;


CREATE OR REPLACE FUNCTION es_update_contact.enqueue_contact_trigger()

  RETURNS TRIGGER AS

$BODY$
  DECLARE
  BEGIN

    -- on duplicate work item, do nothing
    PERFORM es_update_contact.enqueue_contact(NEW.org_id, NEW.id);

    RETURN NEW;

  END;
  $BODY$
  LANGUAGE plpgsql VOLATILE ;

CREATE OR REPLACE FUNCTION es_update_contact.enqueue_values_trigger()

  RETURNS TRIGGER AS

$BODY$
  DECLARE
  BEGIN

    -- on duplicate work item, do nothing
    PERFORM es_update_contact.enqueue_contact(NEW.org_id, NEW.contact_id);

    RETURN NEW;

  END;
  $BODY$
  LANGUAGE plpgsql VOLATILE ;


CREATE TRIGGER sync_es_contact AFTER INSERT OR UPDATE ON public.contacts_contact
  FOR EACH ROW EXECUTE PROCEDURE es_update_contact.enqueue_contact_trigger();

CREATE TRIGGER sync_es_contact AFTER INSERT OR UPDATE ON public.values_value
  FOR EACH ROW EXECUTE PROCEDURE es_update_contact.enqueue_values_trigger();

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


-- ALTER TABLE contacts_contact ADD _fields JSONB default '{}'::JSONB;
-- ALTER TABLE contacts_contact ADD _urns text[];
-- ALTER TABLE contacts_contact ADD _groups text[];


-- CREATE OR REPLACE FUNCTION es_update_contact.serialize_contact_fields(i_org_id INTEGER, i_contact_id INTEGER)
--
--   RETURNS RECORD AS
--
-- $BODY$
--   DECLARE
--     v_query TEXT;
--     v_field RECORD;
--
--     q_fields text[];
--     q_cte_list text[];
--     q_field_values text[];
--     q_field_predicates text[];
--
--     t_query text;
--     t_result RECORD;
--   BEGIN
--
--         v_query := format($query$
-- with contact_urn AS (
--   select contact.id as contact_id, array_agg(cu.identity ORDER BY priority DESC, cu.id) as urns
--   FROM contacts_contact AS contact LEFT JOIN contacts_contacturn cu ON contact.id = cu.contact_id
--     where contact.id = %L
--   group by contact.id
-- ),
--   contact_groups AS (
--     select contact.id as contact_id, array_agg(cg.name ORDER BY cg.id) as groups
--     FROM contacts_contact contact left join contacts_contactgroup_contacts ccc ON contact.id = ccc.contact_id
--   INNER JOIN contacts_contactgroup cg ON ccc.contactgroup_id = cg.id
--       where contact.id = %L AND ccc.contact_id = %L
--     GROUP BY contact.id
--   ), $query$, i_contact_id, i_contact_id, i_contact_id);
--
--     -- read contact field definition for specified org
--     t_query := format($$SELECT id, key, value_type FROM public.contacts_contactfield WHERE org_id = %L AND is_active = TRUE ORDER BY id$$, i_org_id);
--
--     FOR v_field in execute t_query LOOP
--
--       q_fields := array_append(q_fields, format($$%I$$, v_field.key));
--       q_field_values := array_append(q_field_values, format($$%L, %I.value$$, v_field.key, v_field.key));
--       q_field_predicates := array_append(q_field_predicates, format($$%I ON contact.id = %I.contact_id$$, v_field.key, v_field.key));
--
--
--       IF v_field.value_type = 'T' THEN
--         q_cte_list := array_append(q_cte_list, format(
--           $$%I AS (
--           select contact_id, string_value as value
--           from public.values_value
--           WHERE org_id = %L AND contact_field_id = %L AND contact_id = %L
--           ORDER BY 1,2)$$, v_field.key, i_org_id, v_field.id, i_contact_id
--         ));
--       ELSEIF v_field.value_type = 'N' THEN
--         q_cte_list := array_append(q_cte_list, format(
--           $$%I AS (
--           select contact_id, decimal_value as value
--           from public.values_value
--           WHERE org_id = %L AND contact_field_id = %L AND contact_id = %L
--           ORDER BY 1,2)$$, v_field.key, i_org_id, v_field.id, i_contact_id
--         ));
--         ELSEIF v_field.value_type = 'D' THEN
--         q_cte_list := array_append(q_cte_list, format(
--           $$%I AS (
--           select contact_id, datetime_value as value
--           from public.values_value
--           WHERE org_id = %L AND contact_field_id = %L AND contact_id = %L
--           ORDER BY 1,2)$$, v_field.key, i_org_id, v_field.id, i_contact_id
--         ));
--         ELSEIF v_field.value_type = any('{W, I, S}') THEN
--         q_cte_list := array_append(q_cte_list, format(
--           $$%I AS (
--           select contact_id, path as value
--           from public.values_value JOIN locations_adminboundary on values_value.location_value_id = locations_adminboundary.id
--           WHERE org_id = %L AND contact_field_id = %L AND contact_id = %L
--           ORDER BY 1,2)$$, v_field.key, i_org_id, v_field.id, i_contact_id
--         ));
--       END IF;
--     END LOOP;
--
--     v_query := v_query || array_to_string(q_cte_list, ', ');
--
--     v_query := v_query || format($$
--     select
--             contact.id as id,
--             contact_urn.urns,
--             contact_groups.groups,
--             jsonb_build_object(
--                 %s
--             ) as fields
-- $$, array_to_string(q_field_values, ', '));
--
--
--     v_query := v_query || format($$
-- FROM contacts_contact as contact LEFT JOIN contact_urn ON contact.id = contact_urn.contact_id LEFT JOIN contact_groups ON contact.id = contact_groups.contact_id LEFT JOIN %s
-- WHERE contact.id = %L
-- ORDER BY id$$, array_to_string(q_field_predicates, ' LEFT JOIN '), i_contact_id);
--
--
--     EXECUTE v_query INTO t_result;
--
--     return t_result;
--
--   END;
--   $BODY$
--   LANGUAGE plpgsql STABLE;



-- update existing contacts
-- WITH sub AS (
--   SELECT cc.id, scf._urns, scf._groups, scf._fields
-- FROM contacts_contact cc INNER JOIN LATERAL es_update_contact.serialize_contact_fields(cc.org_id, cc.id) as scf(contact_id int, _urns varchar[], _groups varchar[], _fields jsonb) ON TRUE
-- )
-- UPDATE contacts_contact SET _fields = sub._fields, _urns= sub._urns, _groups = sub._groups FROM sub WHERE contacts_contact.id = sub.id;


--
-- CREATE OR REPLACE FUNCTION es_update_contact.update_contact_fields(i_contact_id integer, i_fields jsonb)
--     RETURNS void AS
-- $BODY$
--   DECLARE
--
--   BEGIN
--     UPDATE public.contacts_contact SET _fields = _fields || i_fields WHERE id = i_contact_id;
--   END;
--   $BODY$
--   LANGUAGE plpgsql VOLATILE;
--
--
-- CREATE OR REPLACE FUNCTION es_update_contact.update_contact(i_contact_id integer, i_urns varchar[], i_groups varchar[], i_fields jsonb)
--     RETURNS void AS
-- $BODY$
--   DECLARE
--
--   BEGIN
--     UPDATE public.contacts_contact SET _urns = i_urns, _groups = i_groups, _fields = _fields || i_fields WHERE id = i_contact_id;
--   END;
--   $BODY$
--   LANGUAGE plpgsql VOLATILE;



-- CREATE OR REPLACE FUNCTION es_update_contact.enqueue_contact_direct()
--
--   RETURNS TRIGGER AS
--
-- $BODY$
--   DECLARE
--   BEGIN
--
--     INSERT INTO es_update_contact.task (contact_pk, contact_org_id, contact_document) SELECT NEW.id, NEW.org_id, jsonb_build_object(
--         'id', NEW.id,
--         'name', NEW.name,
--         'language', NEW.language,
--         'is_blocked', NEW.is_blocked,
--         'is_stopped', NEW.is_stopped,
--         'is_test', NEW.is_test,
--         'is_active', NEW.is_active,
--         'urns', NEW._urns,
--         'groups', NEW._groups,
--         'fields', NEW._fields
--     );
--
--     RETURN NEW;
--
--   END;
--   $BODY$
--   LANGUAGE plpgsql VOLATILE;



-- CREATE TRIGGER sync_es_contact_direct AFTER INSERT OR UPDATE OF name, _fields, _urns, _groups, language, is_blocked, is_stopped, is_test, is_active ON public.contacts_contact
--   FOR EACH ROW
-- EXECUTE PROCEDURE es_update_contact.enqueue_contact_direct();

-- DROP TRIGGER sync_es_contact_direct ON public.contacts_contact;

-- DO $BODY$
-- DECLARE
--   v_id integer;
-- BEGIN
-- FOR v_id IN 1..10000 LOOP
--   update contacts_contact set _fields = _fields || '{"age": 66}'::jsonb where id=v_id;
-- END LOOP;
-- END;
-- $BODY$;

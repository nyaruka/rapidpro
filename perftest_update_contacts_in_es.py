from __future__ import unicode_literals, absolute_import, division, print_function

import random
import time

from elasticsearch import Elasticsearch

import django
from django.db import connection


django.setup()  # NOQA

from temba.orgs.models import Org

SQL = '''
CREATE UNLOGGED TABLE IF NOT EXISTS tmp_contacts AS
select row.id, row_to_json(row) as contact FROM (

with contact_urn AS (
  select contact.id, array_agg(cu.identity ORDER BY priority DESC, cu.id) as urns
  FROM contacts_contact AS contact LEFT JOIN contacts_contacturn cu ON contact.id = cu.contact_id
    where contact.org_id = 1
  group by contact.id
),
  contact_groups AS (
    select contact.id, array_agg(c3.name ORDER BY c3.id) as groups
    FROM contacts_contact contact left join contacts_contactgroup_contacts ccc ON contact.id = ccc.contact_id
  INNER JOIN contacts_contactgroup c3 ON ccc.contactgroup_id = c3.id
      where contact.org_id = 1
    GROUP BY contact.id
  ),
string_val as (
   SELECT *
  FROM crosstab($$
select contact_id, contact_field_id, string_value
from public.values_value
WHERE org_id = 1 AND contact_field_id IN (1, 2, 3, 4, 5, 6, 7, 8, 10, 16, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33)
ORDER BY 1,2$$,
$$select id from public.contacts_contactfield
where org_id = 1 and id IN (1, 2, 3, 4, 5, 6, 7, 8, 10, 16, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33) order by id$$) AS (contact_id INT, zipcode text, state text, representative text, senator_junior text, senator_senior text, senator_junior_fax text, senator_senior_fax text, postal_address text, representative_fax text, test_mode text, last_fax_pdf text, mvp2_email_address text, senator_junior_party text, senator_senior_party text, representative_party text, last_fax_pdf_2 text, last_fax_pdf_3 text, last_fax_png text, last_fax_png_2 text, last_fax_png_3 text)
),
  numeric_val as (
    select * from crosstab($$
select contact_id, contact_field_id, decimal_value
from public.values_value
WHERE org_id = 1 AND contact_field_id IN (20, 76, 77, 79, 81, 82, 83, 97, 106, 108, 135)
ORDER BY 1,2$$,
$$select id from public.contacts_contactfield
where org_id = 1 and id IN (20, 76, 77, 79, 81, 82, 83, 97, 106, 108, 135) ORDER BY id$$) as (contact_id int, total_faxes_sent numeric, total_calls_made numeric, total_letters_mailed numeric, total_emails_sent numeric, latitude numeric, longitude numeric, address_changes numeric, name_changes numeric, total_editorials_submitted numeric, letters_sent_today numeric, income numeric)
  ),
  datetime_val as (
    select * from crosstab($$
select contact_id, contact_field_id, datetime_value
from public.values_value
WHERE org_id = 1 AND contact_field_id IN (78, 90, 94, 95, 105, 107)
ORDER BY 1,2$$,
$$select id from public.contacts_contactfield
where org_id = 1 and id IN (78, 90, 94, 95, 105, 107) ORDER BY id$$) as (contact_id int, last_action_date timestamp, registered timestamp, birthday timestamp, v5 timestamp, last_letter_to_the_editor timestamp, last_donation_ask timestamp)
  )

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
            -- we cannot pass more than a 100 arguments to a function
            jsonb_build_object(
                'zipcode', string_val.zipcode,
                'state', string_val.state,
                'representative', string_val.representative,
                'senator_junior', string_val.senator_junior,
                'senator_senior', string_val.senator_senior,
                'senator_junior_fax', string_val.senator_junior_fax,
                'senator_senior_fax', string_val.senator_senior_fax,
                'postal_address', string_val.postal_address,
                'representative_fax', string_val.representative_fax,
                'test_mode', string_val.test_mode,
                'last_fax_pdf', string_val.last_fax_pdf,
                'mvp2_email_address', string_val.mvp2_email_address,
                'senator_junior_party', string_val.senator_junior_party,
                'senator_senior_party', string_val.senator_senior_party,
                'representative_party', string_val.representative_party,
                'last_fax_pdf_2', string_val.last_fax_pdf_2,
                'last_fax_pdf_3', string_val.last_fax_pdf_3,
                'last_fax_png', string_val.last_fax_png,
                'last_fax_png_2', string_val.last_fax_png_2,
                'last_fax_png_3', string_val.last_fax_png_3,
                'total_faxes_sent', numeric_val.total_faxes_sent,
                'total_calls_made', numeric_val.total_calls_made,
                'total_letters_mailed', numeric_val.total_letters_mailed,
                'total_emails_sent', numeric_val.total_emails_sent,
                'latitude', numeric_val.latitude,
                'longitude', numeric_val.longitude,
                'address_changes', numeric_val.address_changes,
                'name_changes', numeric_val.name_changes,
                'total_editorials_submitted', numeric_val.total_editorials_submitted,
                'letters_sent_today', numeric_val.letters_sent_today,
                'income', numeric_val.income,
                'last_action_date', datetime_val.last_action_date,
                'registered', datetime_val.registered,
                'birthday', datetime_val.birthday,
                'v5', datetime_val.v5,
                'last_letter_to_the_editor', datetime_val.last_letter_to_the_editor,
                'last_donation_ask', datetime_val.last_donation_ask

            ) as fields

from contacts_contact AS contact LEFT JOIN contact_urn
    ON contact.id = contact_urn.id
  LEFT JOIN contact_groups ON contact.id = contact_groups.id
  LEFT JOIN string_val ON string_val.contact_id = contact.id
  LEFT JOIN numeric_val ON numeric_val.contact_id = contact.id
  LEFT JOIN datetime_val ON datetime_val.contact_id = contact.id

where contact.org_id = 1
order by id) as row
;'''


if __name__ == '__main__':
    # init ES
    es = Elasticsearch('http://localhost:9200')

    # choose Org
    org = Org.objects.get(pk=1)

    # print('Counting...', end='')
    # contact_id_range = Contact.objects.filter(org=org).aggregate(Max('id'), Min('id'))
    # min_contact_id = contact_id_range['id__min']
    # max_contact_id = contact_id_range['id__max']

    min_contact_id = 1
    max_contact_id = 4167064

    # total_contacts = Contact.objects.filter(org=org).count()
    # print('done!')

    print('Preparing temporary unlogged table ', end='')
    sql_start_time = time.time()
    with connection.cursor() as cur:
        cur.execute(SQL)
    print('... done, total time:', time.time() - sql_start_time)

    print('Indexing...')
    limit = 50000

    times = []

    num_contacts = 1000

    for _id in xrange(1, num_contacts + 1):
        contact_id = random.randint(min_contact_id, max_contact_id)
        with connection.cursor() as cur:
            cur.execute('select * from tmp_contacts where id =%s', (contact_id, ))
            try:
                document_body = cur.fetchone()[1]
            except TypeError:
                continue
        es_time = time.time()
        es.index(index='org_1', doc_type='contact', id=1, body=document_body, timeout='1s')
        times.append(time.time() - es_time)

    print(sum(times) / num_contacts)

    # execute in parallel using xargs
    # seq 2| xargs -P 2 -n 1 python -u perftest_update_contacts_in_es.py

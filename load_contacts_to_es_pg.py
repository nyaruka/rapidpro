from __future__ import unicode_literals, absolute_import, division, print_function

import time

import datetime
import pytz

from elasticsearch import Elasticsearch

import django
from django.db import connection
from django.db.models import Max, Min

django.setup()  # NOQA

from temba.contacts.models import Contact

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


# pivot query to capture all active fields on resistbot, value_type = 'Text'
#
# string_val as (
#   SELECT *
#   FROM crosstab($$
# select contact_id, contact_field_id, string_value
# from public.values_value
# WHERE org_id = 1 AND contact_field_id IN (1, 2, 3, 4, 5, 6, 7, 8, 10, 16, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 38, 39, 40, 44, 45, 51, 80, 84, 85, 86, 87, 93, 96, 98, 99, 100, 101, 102, 103, 104, 110, 117, 118, 119, 120, 121, 122, 123, 127, 128, 129, 130, 131, 132, 133, 134, 136, 137, 138, 207, 208, 210, 211, 212, 213, 215, 216)
# ORDER BY 1,2$$,
# $$select id from public.contacts_contactfield
# where org_id = 1 and id IN (1, 2, 3, 4, 5, 6, 7, 8, 10, 16, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 38, 39, 40, 44, 45, 51, 80, 84, 85, 86, 87, 93, 96, 98, 99, 100, 101, 102, 103, 104, 110, 117, 118, 119, 120, 121, 122, 123, 127, 128, 129, 130, 131, 132, 133, 134, 136, 137, 138, 207, 208, 210, 211, 212, 213, 215, 216) order by id$$) AS (contact_id INT, zipcode text, state text, representative text, senator_junior text, senator_senior text, senator_junior_fax text, senator_senior_fax text, postal_address text, representative_fax text, test_mode text, last_fax_pdf text, mvp2_email_address text, senator_junior_party text, senator_senior_party text, representative_party text, last_fax_pdf_2 text, last_fax_pdf_3 text, last_fax_png text, last_fax_png_2 text, last_fax_png_3 text, mvp3_signature_url text, salutation text, governor text, governor_fax text, amazon_user_id text, fax_failures text, faxes_in_progress text, last_email_message text, address_1 text, address_2 text, city text, zip_plus_4 text, swingleft text, v4_address_input text, letter text, last_letter text, congressional_district text, address_last_line text, time_zone text, county text, mayor text, mailto text, governor_party text, senator_senior_phone text, senator_junior_phone text, governor_phone text, representative_phone text, gotv text, gotv_time_of_day text, polling_place_name text, polling_place_address text, polling_place_city text, polling_place_zip text, polling_place_hours text, polling_place_notes text, last_invited text, total_hand_deliveries text, invitations text, swingleft_token text, last_event_alert text, opted_out text, state_representative text, state_senator text, district_upper text, district_lower text, state_representative_phone text, state_senator_phone text, target text)
# )

# jsonb_build_object(
#     'zipcode', string_val.zipcode,
#     'state', string_val.state,
#     'representative', string_val.representative,
#     'senator_junior', string_val.senator_junior,
#     'senator_senior', string_val.senator_senior,
#     'senator_junior_fax', string_val.senator_junior_fax,
#     'senator_senior_fax', string_val.senator_senior_fax,
#     'postal_address', string_val.postal_address,
#     'representative_fax', string_val.representative_fax,
#     'test_mode', string_val.test_mode,
#     'last_fax_pdf', string_val.last_fax_pdf,
#     'mvp2_email_address', string_val.mvp2_email_address,
#     'senator_junior_party', string_val.senator_junior_party,
#     'senator_senior_party', string_val.senator_senior_party,
#     'representative_party', string_val.representative_party,
#     'last_fax_pdf_2', string_val.last_fax_pdf_2,
#     'last_fax_pdf_3', string_val.last_fax_pdf_3,
#     'last_fax_png', string_val.last_fax_png,
#     'last_fax_png_2', string_val.last_fax_png_2,
#     'last_fax_png_3', string_val.last_fax_png_3) | |
# jsonb_build_object(
#     'mvp3_signature_url', string_val.mvp3_signature_url,
#     'salutation', string_val.salutation,
#     'governor', string_val.governor,
#     'governor_fax', string_val.governor_fax,
#     'amazon_user_id', string_val.amazon_user_id,
#     'fax_failures', string_val.fax_failures,
#     'faxes_in_progress', string_val.faxes_in_progress,
#     'last_email_message', string_val.last_email_message,
#     'address_1', string_val.address_1,
#     'address_2', string_val.address_2,
#     'city', string_val.city,
#     'zip_plus_4', string_val.zip_plus_4,
#     'swingleft', string_val.swingleft,
#     'v4_address_input', string_val.v4_address_input,
#     'letter', string_val.letter,
#     'last_letter', string_val.last_letter,
#     'congressional_district', string_val.congressional_district,
#     'address_last_line', string_val.address_last_line,
#     'time_zone', string_val.time_zone,
#     'county', string_val.county,
#     'mayor', string_val.mayor,
#     'mailto', string_val.mailto,
#     'governor_party', string_val.governor_party,
#     'senator_senior_phone', string_val.senator_senior_phone,
#     'senator_junior_phone', string_val.senator_junior_phone,
#     'governor_phone', string_val.governor_phone,
#     'representative_phone', string_val.representative_phone,
#     'gotv', string_val.gotv,
#     'gotv_time_of_day', string_val.gotv_time_of_day,
#     'polling_place_name', string_val.polling_place_name,
#     'polling_place_address', string_val.polling_place_address,
#     'polling_place_city', string_val.polling_place_city) | |
# jsonb_build_object(
#     'polling_place_zip', string_val.polling_place_zip,
#     'polling_place_hours', string_val.polling_place_hours,
#     'polling_place_notes', string_val.polling_place_notes,
#     'last_invited', string_val.last_invited,
#     'total_hand_deliveries', string_val.total_hand_deliveries,
#     'invitations', string_val.invitations,
#     'swingleft_token', string_val.swingleft_token,
#     'last_event_alert', string_val.last_event_alert,
#     'opted_out', string_val.opted_out,
#     'state_representative', string_val.state_representative,
#     'state_senator', string_val.state_senator,
#     'district_upper', string_val.district_upper,
#     'district_lower', string_val.district_lower,
#     'state_representative_phone', string_val.state_representative_phone,
#     'state_senator_phone', string_val.state_senator_phone,
#     'target', string_val.target,
#     'total_faxes_sent', numeric_val.total_faxes_sent,
#     'total_calls_made', numeric_val.total_calls_made,
#     'total_letters_mailed', numeric_val.total_letters_mailed,
#     'total_emails_sent', numeric_val.total_emails_sent,
#     'latitude', numeric_val.latitude,
#     'longitude', numeric_val.longitude,
#     'address_changes', numeric_val.address_changes,
#     'name_changes', numeric_val.name_changes,
#     'total_editorials_submitted', numeric_val.total_editorials_submitted,
#     'letters_sent_today', numeric_val.letters_sent_today,
#     'income', numeric_val.income,
#     'last_action_date', datetime_val.last_action_date,
#     'registered', datetime_val.registered,
#     'birthday', datetime_val.birthday,
#     'v5', datetime_val.v5,
#     'last_letter_to_the_editor', datetime_val.last_letter_to_the_editor,
#     'last_donation_ask', datetime_val.last_donation_ask
#
# ) as fields


# pivot query for location value_type
#
# location type
# ,
#   location_val as (
#     select * from crosstab($$
# select contact_id, contact_field_id, path
# from public.values_value JOIN locations_adminboundary on values_value.location_value_id = locations_adminboundary.id
# WHERE org_id = 1 AND contact_field_id IN (4,5,6)
# ORDER BY 1,2$$,
# $$select id from public.contacts_contactfield
# where org_id = 1 and id IN (4,5,6)
# ORDER by id$$) as (contact_id int, ward text, district text, state text)
#   )

# alternative way to create json objects
#
# jsonb_object(
#                 '{zipcode, state, representative, senator_junior, senator_senior, senator_junior_fax, senator_senior_fax, postal_address, representative_fax, test_mode, last_fax_pdf, mvp2_email_address, senator_junior_party, senator_senior_party, representative_party, last_fax_pdf_2, last_fax_pdf_3, last_fax_png, last_fax_png_2, last_fax_png_3, mvp3_signature_url, salutation, governor, governor_fax, amazon_user_id, fax_failures, faxes_in_progress, last_email_message, address_1, address_2, city, zip_plus_4, swingleft, v4_address_input, letter, last_letter, congressional_district, address_last_line, time_zone, county, mayor, mailto, governor_party, senator_senior_phone, senator_junior_phone, governor_phone, representative_phone, gotv, gotv_time_of_day, polling_place_name, polling_place_address, polling_place_city, polling_place_zip, polling_place_hours, polling_place_notes, last_invited, total_hand_deliveries, invitations, swingleft_token, last_event_alert, opted_out, state_representative, state_senator, district_upper, district_lower, state_representative_phone, state_senator_phone, target, total_faxes_sent, total_calls_made, total_letters_mailed, total_emails_sent, latitude, longitude, address_changes, name_changes, total_editorials_submitted, letters_sent_today, income, last_action_date, registered, birthday, v5, last_letter_to_the_editor, last_donation_ask}',
#                 '{string_val.zipcode, string_val.state, string_val.representative, string_val.senator_junior, string_val.senator_senior, string_val.senator_junior_fax, string_val.senator_senior_fax, string_val.postal_address, string_val.representative_fax, string_val.test_mode, string_val.last_fax_pdf, string_val.mvp2_email_address, string_val.senator_junior_party, string_val.senator_senior_party, string_val.representative_party, string_val.last_fax_pdf_2, string_val.last_fax_pdf_3, string_val.last_fax_png, string_val.last_fax_png_2, string_val.last_fax_png_3, string_val.mvp3_signature_url, string_val.salutation, string_val.governor, string_val.governor_fax, string_val.amazon_user_id, string_val.fax_failures, string_val.faxes_in_progress, string_val.last_email_message, string_val.address_1, string_val.address_2, string_val.city, string_val.zip_plus_4, string_val.swingleft, string_val.v4_address_input, string_val.letter, string_val.last_letter, string_val.congressional_district, string_val.address_last_line, string_val.time_zone, string_val.county, string_val.mayor, string_val.mailto, string_val.governor_party, string_val.senator_senior_phone, string_val.senator_junior_phone, string_val.governor_phone, string_val.representative_phone, string_val.gotv, string_val.gotv_time_of_day, string_val.polling_place_name, string_val.polling_place_address, string_val.polling_place_city, string_val.polling_place_zip, string_val.polling_place_hours, string_val.polling_place_notes, string_val.last_invited, string_val.total_hand_deliveries, string_val.invitations, string_val.swingleft_token, string_val.last_event_alert, string_val.opted_out, string_val.state_representative, string_val.state_senator, string_val.district_upper, string_val.district_lower, string_val.state_representative_phone, string_val.state_senator_phone, string_val.target, numeric_val.total_faxes_sent, numeric_val.total_calls_made, numeric_val.total_letters_mailed, numeric_val.total_emails_sent, numeric_val.latitude, numeric_val.longitude, numeric_val.address_changes, numeric_val.name_changes, numeric_val.total_editorials_submitted, numeric_val.letters_sent_today, numeric_val.income, datetime_val.last_action_date,datetime_val.registered,datetime_val.birthday,datetime_val.v5,datetime_val.last_letter_to_the_editor,datetime_val.last_donation_ask}'
#             )


total_imported_contacts_count = 0


def contact_serializator(total_contacts, start_id, end_id, page_id):
    global total_imported_contacts_count

    print('Executing SQL...', 'Page: ', page_id, '(', start_id, '=>', end_id, ')', sep='', end='')
    with connection.cursor() as cur:
        sql_start_time = time.time()

        cur.execute(
            'SELECT contact from tmp_contacts WHERE id >= %s AND id < %s', (start_id, end_id)
        )
        print('...in...', time.time() - sql_start_time, '...done!', sep='')

        start_time = time.time()
        for num, contact_row in enumerate(cur, start=total_imported_contacts_count):

            yield contact_row[0]

            chunk_size = 20000
            if num % chunk_size == 0:
                elapsed = time.time() - start_time

                estimated = datetime.datetime.fromtimestamp(
                    time.time() + ((total_contacts - num) / chunk_size) * elapsed, tz=pytz.timezone('CET')).isoformat()

                print('indexed {}/{} contacts, {} eta: {}'.format(num, total_contacts, elapsed, estimated))
                start_time = time.time()

        print('indexed {} contacts'.format(num))
        total_imported_contacts_count = num


org_1_index = {
    "mappings": {
        "contact": {
            "properties": {
                "fields": {
                    "properties": {
                        "address_changes": {
                            "type": "float"
                        },
                        "birthday": {
                            "type": "date"
                        },
                        "income": {
                            "type": "float"
                        },
                        "last_action_date": {
                            "type": "date"
                        },
                        "last_donation_ask": {
                            "type": "date"
                        },
                        "last_fax_pdf": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "last_fax_pdf_2": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "last_fax_pdf_3": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "last_fax_png": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "last_fax_png_2": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "last_fax_png_3": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "last_letter_to_the_editor": {
                            "type": "date"
                        },
                        "latitude": {
                            "type": "float"
                        },
                        "letters_sent_today": {
                            "type": "float"
                        },
                        "longitude": {
                            "type": "float"
                        },
                        "mvp2_email_address": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "name_changes": {
                            "type": "float"
                        },
                        "postal_address": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "registered": {
                            "type": "date"
                        },
                        "representative": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "representative_fax": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "representative_party": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "senator_junior": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "senator_junior_fax": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "senator_junior_party": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "senator_senior": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "senator_senior_fax": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "senator_senior_party": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "state": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "test_mode": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "total_calls_made": {
                            "type": "float"
                        },
                        "total_editorials_submitted": {
                            "type": "float"
                        },
                        "total_emails_sent": {
                            "type": "float"
                        },
                        "total_faxes_sent": {
                            "type": "float"
                        },
                        "total_letters_mailed": {
                            "type": "float"
                        },
                        "v5": {
                            "type": "date"
                        },
                        "zipcode": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        }
                    }
                },
                "groups": {
                    "type": "text",
                    "fields": {
                        "keyword": {
                            "type": "keyword",
                            "ignore_above": 256
                        }
                    }
                },
                "id": {
                    "type": "long"
                },
                "is_active": {
                    "type": "boolean"
                },
                "is_blocked": {
                    "type": "boolean"
                },
                "is_stopped": {
                    "type": "boolean"
                },
                "is_test": {
                    "type": "boolean"
                },
                "language": {
                    "type": "text",
                    "fields": {
                        "keyword": {
                            "type": "keyword",
                            "ignore_above": 256
                        }
                    }
                },
                "name": {
                    "type": "text",
                    "fields": {
                        "keyword": {
                            "type": "keyword",
                            "ignore_above": 256
                        }
                    }
                },
                "urns": {
                    "type": "text",
                    "fields": {
                        "keyword": {
                            "type": "keyword",
                            "ignore_above": 256
                        }
                    }
                }
            }
        }
    },
    "settings": {
        "index": {
            "number_of_shards": "5",
            "number_of_replicas": "1",
            "analysis": {
                "filter": {
                    "trigrams_filter": {
                        "type": "ngram",
                        "min_gram": 3,
                        "max_gram": 3
                    }
                },
                "analyzer": {
                    "trigrams": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": [
                            "lowercase",
                            "trigrams_filter"
                        ]
                    }
                }
            }
        }
    }
}


def serialize_bulk_operations(contacts):
    for contact in contacts:
        yield {
            "index": {"_index": "org_1", "_type": "contact", "_id": contact['id']}
        }
        yield contact


if __name__ == '__main__':
    # init ES
    es = Elasticsearch('http://localhost:9200')

    # choose Org
    org = Org.objects.get(pk=1)

    # load contact data
    es.indices.delete(index='org_1', ignore=[400, 404])

    # create the index
    es.indices.create(index='org_1', body=org_1_index)

    print('Counting...', end='')
    contact_id_range = Contact.objects.filter(org=org).aggregate(Max('id'), Min('id'))
    min_contact_id = contact_id_range['id__min']
    max_contact_id = contact_id_range['id__max']

    total_contacts = Contact.objects.filter(org=org).count()
    print('done!')

    print('Preparing temporary unlogged table ', end='')
    sql_start_time = time.time()
    with connection.cursor() as cur:
        cur.execute(SQL)
    print('... done, total time:', time.time() - sql_start_time)

    print('Indexing...')
    limit = 50000

    for offset in range(min_contact_id, max_contact_id, limit):
        page_id = (offset // limit) + 1

        es.bulk(
            serialize_bulk_operations(
                contact_serializator(total_contacts, start_id=offset, end_id=offset + limit, page_id=page_id)
            ),
            index='org_1', doc_type='contact'
        )

    # print('Dropping temporary table ', end='')
    # with connection.cursor() as cur:
    #     cur.execute('DROP TABLE tmp_contacts;')
    # print('... done!')

# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import requests
import psycopg2
import json

from django.core.management.base import BaseCommand

CONTACT_QUERY = """
SELECT row_to_json(t) FROM(
    SELECT org_id, uuid, name, language, is_stopped, is_blocked, created_on, modified_on,
    (
        SELECT array_to_json(array_agg(row_to_json(u))) FROM (
            SELECT scheme, path
            FROM contacts_contacturn
            WHERE contact_id=contacts_contact.id
        ) u
    ) as urns,
    (
        SELECT jsonb_agg(f.value) FROM (
            SELECT value||jsonb_build_object('field', key) as value from jsonb_each(contacts_contact.fields)
        ) as f
    ) as fields
    FROM contacts_contact
    WHERE is_test = FALSE and is_active = TRUE
) t
"""

MAPPINGS = """
{
  "properties": {
    "fields": {
      "type": "nested",
      "properties":{
        "field": {
          "type": "keyword"
        },
        "text": {
          "type": "text",
          "fields": {
            "keyword": {
              "type": "keyword",
              "ignore_above": 64
            }
          }
        },
        "decimal": {
          "type": "scaled_float",
          "scaling_factor": 10000
        },
        "datetime": {
          "type": "date"
        },
        "state": {
          "type": "keyword"
        },
        "district": {
          "type": "keyword"
        },
        "ward": {
          "type": "keyword"
        }
      }
    },
    "urns": {
      "type": "nested",
      "properties": {
        "path": {
          "type": "text",
          "fields": {
            "keyword": {
              "type": "keyword",
              "ignore_above": 64
            }
          }
        },
        "scheme": {
          "type": "keyword"
        }
      }
    },
    "uuid": {
      "type": "keyword"
    },
    "language": {
      "type": "keyword"
    }
  }
}
"""


class Command(BaseCommand):
    help = "Loads all contacts in database to a new elasticsearch index"

    def add_arguments(self, parser):
        parser.add_argument('--database',
                            dest='database',
                            required=True,
                            help="The name of the database to connect to")

        parser.add_argument('--index',
                            dest='index',
                            required=True,
                            help="The name of the index to add documents to")

    def handle(self, *args, **options):
        index = options['index']
        db = options['database']
        conn = psycopg2.connect("dbname='%s' host='localhost'" % db)

        # delete the index first
        requests.delete("http://localhost:9200/%s" % index)

        # then create our mappings
        requests.put("http://localhost:9200/%s" % index, json={}).raise_for_status()
        resp = requests.put("http://localhost:9200/%s/_mapping/_doc" % index, json=json.loads(MAPPINGS))
        print(resp.content)
        resp.raise_for_status()

        with conn.cursor(name='contacts') as cursor:
            cursor.itersize = 1000
            cursor.execute(CONTACT_QUERY)

            contacts = []
            count = 0
            for row in cursor:
                contacts.append(row[0])

                # build up our body
                if len(contacts) == 500:
                    body = ""
                    for contact in contacts:
                        body += json.dumps(dict(create={"_id": contact['uuid'], "_type": "_doc"})) + "\n"
                        body += json.dumps(contact) + "\n"

                    resp = requests.post("http://localhost:9200/%s/_bulk" % index, data=body, headers={"Content-Type": "application/json"}).raise_for_status()

                    count += len(contacts)
                    contacts = []
                    print("** synced %d contacts" % count)

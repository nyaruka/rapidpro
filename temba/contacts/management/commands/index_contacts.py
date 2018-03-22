# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import requests
import psycopg2
import json
import datetime
import iso8601
import pytz
import time

from django.conf import settings
from django.core.management.base import BaseCommand

CONTACT_QUERY = """
SELECT row_to_json(t) FROM(
    SELECT id, org_id, uuid, name, language, is_stopped, is_blocked, created_on, modified_on,
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

INDEX_SETTINGS = """
{
  "settings" : {
    "index" : {
      "number_of_shards" : 5,
      "number_of_replicas" : 0,
      "routing_partition_size": 2
    }
  },

  "mappings": {
    "_doc": {
      "_routing": {
        "required": true
      }
    }
  }
}
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
          "analyzer": "simple",
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
    },
    "name": {
      "type": "text",
      "analyzer": "simple",
      "fields": {
        "keyword": {
          "type": "keyword",
          "ignore_above": 64
        }
      }
    }
  }
}
"""

EPOCH = datetime.datetime.utcfromtimestamp(0).replace(tzinfo=pytz.utc)


class Command(BaseCommand):
    help = "Loads all contacts in database to a new elasticsearch index"

    def add_arguments(self, parser):
        parser.add_argument('--database',
                            dest='database',
                            default=None,
                            help="The name of the database to connect to, defaults to default django db")

        parser.add_argument('--delete',
                            dest='delete',
                            default=False,
                            action='store_true',
                            help="Whether to delete the index first")

        parser.add_argument('--index',
                            dest='index',
                            required=True,
                            help="The name of the index to add documents to")

        parser.add_argument('--url',
                            dest='url',
                            default="http://localhost:9200",
                            help="The host of the elasticsearch server")

    def assertOk(self, resp):
        try:
            resp.raise_for_status()
        except:
            raise Exception("Received error: %s" % resp.content)

        if not resp.json().get('acknowledged') and resp.json().get('errors', True):
            raise Exception("Received error: %s" % resp.content)

    def index_contacts(self, url, index, contacts):
        body = ""
        for contact in contacts:
            # calculate our version from our modified_on
            version = iso8601.parse_date(contact['modified_on'])
            version = int((version - EPOCH).total_seconds() * 1000)

            # clear our NaN decimals
            fields = contact.get('fields', [])
            if fields:
                for field in fields:
                    if field.get('decimal') == 'NaN':
                        del field['decimal']

            body += json.dumps({
                "index": {
                    "_id": contact['id'],
                    "_type": "_doc",
                    "_version": version,
                    "_version_type": "external",
                    "_routing": contact['org_id']
                }
            }) + "\n"
            body += json.dumps(contact) + "\n"

        resp = requests.post("%s/%s/_bulk" % (url, index), data=body,
                             headers={"Content-Type": "application/json"})
        resp.raise_for_status()

        conflicts = 0

        for item in resp.json()['items']:
            if item['index']['status'] == 409:
                conflicts += 1
            elif item['index'].get('error'):
                raise Exception("Received error: %s" % resp.content)

        return conflicts

    def handle(self, *args, **options):
        url = options['url']
        index = options['index']
        db = options['database']

        if db:
            conn = psycopg2.connect(dbname=db, host='localhost')
        else:
            db = settings.DATABASES['direct']
            conn = psycopg2.connect(dbname=db['NAME'], host=db['HOST'], port=db['PORT'], user=db['USER'], password=db['PASSWORD'])

        # delete the index first if asked for
        if options['delete']:
            resp = requests.delete("%s/%s" % (url, index))
            self.assertOk(resp)

            # create our mappings
            requests.put("%s/%s" % (url, index), json=json.loads(INDEX_SETTINGS)).raise_for_status()
            resp = requests.put("%s/%s/_mapping/_doc" % (url, index), json=json.loads(MAPPINGS))
            self.assertOk(resp)

        start = time.time()

        with conn.cursor(name='contacts') as cursor:
            cursor.itersize = 1000
            cursor.execute(CONTACT_QUERY)

            contacts = []
            count = 0
            conflicts = 0

            for row in cursor:
                contacts.append(row[0])

                # build up our body
                if len(contacts) == 100:
                    conflicts += self.index_contacts(url, index, contacts)
                    count += len(contacts)
                    rate = count / float(time.time() - start)

                    if count % 1000 == 0:
                        print("** indexed %d contacts (%d conflicts) %.2f per sec" % (count, conflicts, rate))

                    contacts = []

        if len(contacts) > 0:
            self.index_contacts(url, index, contacts)
            count += len(contacts)

        print("** indexed %d contacts in %d seconds" % (count, time.time() - start))

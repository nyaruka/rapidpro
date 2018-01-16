# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import, division, print_function

import time

import itertools
from elasticsearch import Elasticsearch

from django.db import connection, transaction
import django

django.setup()

es = Elasticsearch('http://localhost:9200')


CONTACTS_IN_BATCH = 1000
CONTACTS_SYNCED = 0


def serialize_bulk_operations(contacts):
    global CONTACTS_SYNCED
    with connection.cursor() as cur:
        for contact_pk, contact_org_id in contacts:

            index_name = 'org_{}'.format(contact_org_id)

            yield {
                'index': {'_index': index_name, '_type': 'contact', '_id': contact_pk}
            }

            cur.execute(
                'select * from es_update_contact.serialize_contact(%s, %s)', (contact_org_id, contact_pk)
            )
            contact_document = cur.fetchone()
            yield contact_document

            CONTACTS_SYNCED += 1


if __name__ == '__main__':
    print('Starting main loop...')
    while True:
        start_time = time.time()

        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(
                    'select contact_pk, contact_org_id from es_update_contact.dequeue_contact(%s)',
                    (CONTACTS_IN_BATCH, )
                )

                operations = serialize_bulk_operations(
                    ((c_id, c_org_id) for c_id, c_org_id in cur)
                )

                # peek into generator to see if we have data for sync
                operation = next(operations, None)

                if operation is not None:
                    print('indexing ', end='')

                    es.bulk(itertools.chain([operation], operations))

                    print(CONTACTS_SYNCED, 'contacts in', time.time() - start_time)

        # wait
        time.sleep(0.250)
        CONTACTS_SYNCED = 0

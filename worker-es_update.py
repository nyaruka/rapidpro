# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import, division, print_function

import json
import time

import itertools
from elasticsearch import Elasticsearch

from django.db import connection, transaction
import django

django.setup()

es = Elasticsearch('http://localhost:9200')


CONTACTS_IN_BATCH = 5000


def serialize_bulk_operations(contacts):
    for contact in contacts:
        index_name = 'org_{}'.format(1)  # contact['org_id']
        contact_id = contact['id']
        yield {
            'index': {'_index': index_name, '_type': 'contact', '_id': contact_id}
        }
        yield contact


if __name__ == '__main__':
    print('Starting main loop...')
    while True:
        start_time = time.time()

        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute('select * from es_update_contact.dequeue_contact(%s)', (CONTACTS_IN_BATCH, ))

                operations = serialize_bulk_operations((json.loads(work_task) for _, _, work_task, _ in cur))

                # peek into generator to see if we have data for sync
                operation = next(operations, None)

                if operation is not None:
                    print('indexing ', end='')

                    es.bulk(itertools.chain([operation], operations), index='org_1', doc_type='contact')

                    print(CONTACTS_IN_BATCH, 'contacts in', time.time() - start_time)

        # wait
        time.sleep(0.250)

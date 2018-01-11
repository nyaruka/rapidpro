from __future__ import unicode_literals, absolute_import, division, print_function

import time

import datetime
import pytz
import six


from elasticsearch import Elasticsearch


import django

django.setup()  # NOQA

from temba.contacts.models import Contact, ContactField
from temba.values.models import Value

from temba.orgs.models import Org


es = Elasticsearch('localhost:9200')

# choose Org
org = Org.objects.get(pk=1)


def serialize_value(field, value):
    if value is None:
        return None
    if field.value_type == Value.TYPE_DATETIME:
        return value.datetime_value.astimezone(org.timezone).isoformat() if value.datetime_value else None
    elif field.value_type == Value.TYPE_DECIMAL:
        if value.decimal_value is None:
            return None

        as_int = int(value.decimal_value.to_integral_value())
        is_int = value.decimal_value == as_int
        return as_int if is_int else float(value.decimal_value)
    elif field.value_type in [Value.TYPE_STATE, Value.TYPE_DISTRICT, Value.TYPE_WARD] and value.location_value:
        return value.location_value.path
    else:
        return value.string_value


def contact_serializator():
    print('init contact', end='')
    contacts = Contact.objects.filter(org=org).order_by('id').iterator()

    total_contacts = Contact.objects.filter(org=org).count()

    fields = ContactField.objects.filter(org=org, is_active=True)

    print('...bulk cache', end='')
    # Contact.bulk_cache_initialize(org, contacts)
    print('...done')

    start_time = time.time()
    for num, contact in enumerate(contacts, start=1):
        field_data = {}
        for contact_field in fields:
            value = contact.get_field(contact_field.key)
            field_data[contact_field.key] = serialize_value(contact_field, value)

        groups = (
            contact.prefetched_user_groups if hasattr(contact, 'prefetched_user_groups') else contact.user_groups.all()
        )

        yield {
            'id': contact.id,
            'name': contact.name,
            'language': contact.language,
            'urns': [six.text_type(urn) for urn in contact.get_urns()],
            'groups': [g.name for g in groups],
            'fields': field_data,
            'is_blocked': contact.is_blocked,
            'is_stopped': contact.is_stopped,
            'is_test': contact.is_test,
            'is_active': contact.is_active,
        }
        chunk_size = 500
        if num % chunk_size == 0:
            elapsed = time.time() - start_time

            estimated = datetime.datetime.fromtimestamp(
                time.time() + ((total_contacts - num) / chunk_size) * elapsed, tz=pytz.timezone('CET')).isoformat()

            print('indexed {}/{} contacts, {} eta: {}'.format(num, total_contacts, elapsed, estimated))
            start_time = time.time()

    print('indexed {} contacts'.format(num))


# load contact data
es.indices.delete(index='org_1', ignore=[400, 404])

org_1_index = {
    "mappings": {
        "contact": {
            "properties": {
                "fields": {
                    "properties": {
                        "age": {
                            "type": "long"
                        },
                        "district": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "gender": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "joined": {
                            "type": "date"
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
                        "ward": {
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

# create the index
es.indices.create(index='org_1', body=org_1_index)


def serialize_bulk_operations(contacts):
    for contact in contacts:
        yield {
            "index": {"_index": "org_1", "_type": "contact", "_id": contact['id']}
        }
        yield contact


print('Indexing...')

es.bulk(serialize_bulk_operations(contact_serializator()), index='org_1', doc_type='contact')

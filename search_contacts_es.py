import time

from elasticsearch import Elasticsearch

es = Elasticsearch('localhost:9200')

# 'match' executes full-text search on key 'name'
# res = es.search(index='org_1', body={
#     'query': {
#         'match': {
#             'name': 'Dave'
#         }
#     }
# })

# 'term' executes exact search on key 'blocked'
# res = es.search(index='org_1', body={
#     'query': {
#         'term': {
#             'blocked': True
#         }
#     }
# })


# 'select' specific fields and sort results
# {
# "query": {
#   "match": {
#     "name" : "Igor"
#   }
# },
# "_source": ["name", "fields.age"],
# "sort": {
#   "fields.age": { "order": "desc" }
# }
# }


query = {
    "query": {
        "bool": {
            "must": [
                {"range": {"fields.age": {"gt": 70}}},
                {"term": {"is_blocked": False}},
                {"term": {"is_active": True}},
                {"term": {"is_stopped": False}}
            ]
        }
    }
}


# contact search for `name is Dave or tel has 250700009`
# wildcard search is 'expensive' but using `trigrams` analyzer on URNs does not produce same results as in the database
# `name.keyword` index is used when we want to exactly match a 'term'
# expressions in *filter* section do not contribute to the **relevance** index and should be exact
query_1 = {
    "query": {
        "bool": {
            "must": [{
                "bool": {
                    "should": [
                        {"wildcard": {
                            "urns": "*250700009*"
                        }},
                        {"match": {"name.keyword": "Dave"}},
                    ]
                }},
            ],
            "filter": [
                {"term": {"is_blocked": False}},
                {"term": {"is_active": True}},
                {"term": {"is_stopped": False}}
            ]
        }
    }
}

query_resist_1 = {
    "query": {
        "bool": {
            "must": [{
                "bool": {
                    "must": [
                        {"match": {"fields.state.keyword": "CA"}},
                        {"range": {
                            "fields.total_emails_sent": {
                                "gte": 3
                            }
                        }},
                    ]
                }},
            ],
            "filter": [
                {"term": {"is_blocked": False}},
                {"term": {"is_active": True}},
                {"term": {"is_stopped": False}}
            ]
        }
    }
}


start = time.time()

res = es.search(
    index='org_1', body=query_resist_1, size=10
)

print(time.time() - start)

print('Got %d Hits:' % res['hits']['total'])
print([(hit['_id'], hit['_score']) for hit in res['hits']['hits']])

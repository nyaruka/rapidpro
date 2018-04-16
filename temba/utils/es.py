# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

from django.conf import settings

from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search as es_Search


ES = Elasticsearch(hosts=[settings.ELASTICSEARCH_URL])


class ModelESSearch(es_Search):
    """
    * add Django model information to the elasticserach_dsl Search class
    * simulate an empty Elasticsearch response with 'none()' method that short-circuits execution and returns no data
    """

    is_none = False

    def __init__(self, **kwargs):
        self.model = kwargs.pop('model', None)

        super(ModelESSearch, self).__init__(**kwargs)

    def _clone(self):
        new_search = super(ModelESSearch, self)._clone()

        # copy extra attributes
        new_search.model = self.model
        new_search.is_none = self.is_none

        return new_search

    def execute(self, ignore_cache=False):
        if self.is_none:
            return self._response_class(
                search=self,
                response={
                    "_shards": {
                        "failed": 0,
                        "successful": 10,
                        "total": 10
                    },
                    'hits': {'hits': []},
                    "timed_out": False,
                    "took": 1
                }
            )
        else:
            return super(ModelESSearch, self).execute(ignore_cache)

    def count(self):
        if self.is_none:
            return 0
        else:
            return super(ModelESSearch, self).count()

    def none(self):
        """
        Simulate an empty ElasticSearch Response
        """
        s = self._clone()

        s.is_none = True
        return s

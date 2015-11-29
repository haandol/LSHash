# lshash/storage.py
# Copyright 2012 Kay Zhu (a.k.a He Zhu) and contributors (see CONTRIBUTORS.txt)
#
# This module is part of lshash and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

import json

try:
    import redis
except ImportError:
    redis = None

try:
    from elasticsearch import Elasticsearch
    from elasticsearch_dsl import Search
except:
    Elasticsearch = None
    Search = None

__all__ = ['storage']


def storage(storage_config, index):
    """ Given the configuration for storage and the index, return the
    configured storage instance.
    """
    if 'dict' in storage_config:
        return InMemoryStorage(storage_config['dict'])
    elif 'redis' in storage_config:
        storage_config['redis']['db'] = index
        return RedisStorage(storage_config['redis'])
    elif 'elasticsearch' in storage_config:
        return ElasticStorage(storage_config['elasticsearch'])
    else:
        raise ValueError("Only in-memory dictionary and Redis are supported.")


class BaseStorage(object):
    def __init__(self, config):
        """ An abstract class used as an adapter for storages. """
        raise NotImplementedError

    def keys(self):
        """ Returns a list of binary hashes that are used as dict keys. """
        raise NotImplementedError

    def set_val(self, key, val):
        """ Set `val` at `key`, note that the `val` must be a string. """
        raise NotImplementedError

    def get_val(self, key):
        """ Return `val` at `key`, note that the `val` must be a string. """
        raise NotImplementedError

    def append_val(self, key, val):
        """ Append `val` to the list stored at `key`.

        If the key is not yet present in storage, create a list with `val` at
        `key`.
        """
        raise NotImplementedError

    def get_list(self, key):
        """ Returns a list stored in storage at `key`.

        This method should return a list of values stored at `key`. `[]` should
        be returned if the list is empty or if `key` is not present in storage.
        """
        raise NotImplementedError


class InMemoryStorage(BaseStorage):
    def __init__(self, config):
        self.name = 'dict'
        self.storage = dict()

    def keys(self):
        return self.storage.keys()

    def set_val(self, key, val):
        self.storage[key] = val

    def get_val(self, key):
        return self.storage[key]

    def append_val(self, key, val):
        self.storage.setdefault(key, []).append(val)

    def get_list(self, key):
        return self.storage.get(key, [])


class RedisStorage(BaseStorage):
    def __init__(self, config):
        if not redis:
            raise ImportError("redis-py is required to use Redis as storage.")
        self.name = 'redis'
        self.storage = redis.StrictRedis(**config)

    def keys(self, pattern="*"):
        return self.storage.keys(pattern)

    def set_val(self, key, val):
        self.storage.set(key, val)

    def get_val(self, key):
        return self.storage.get(key)

    def append_val(self, key, val):
        self.storage.rpush(key, json.dumps(val))

    def get_list(self, key):
        return self.storage.lrange(key, 0, -1)


class ElasticStorage(BaseStorage):
    def __init__(self, config):
        if not Elasticsearch:
            raise ImportError("elasticsearch-py is required to use Elasticsearch as storage.")
        if not Search:
            raise ImportError("elasticsearch_dsl is required to use Elasticsearch as storage.")

        self.name = 'elasticsearch'
        self.storage = Elasticsearch(**config)

    def keys(self, pattern="*"):
        return self.storage.keys(pattern)

    def set_val(self, key, val):
        body = {
            'key': key,
            'val': ','.join(map(str, val[0])),
            'extra': str(val[1])
        }
        self.storage.index(index='sift', doc_type='sift', body=body)

    def get_val(self, key):
        s = Search(using=self.storage, index='sift')
        return s.filter('term', key=key).execute().hits.hits

    def append_val(self, key, val):
        self.set_val(key, val)

    def get_list(self, key):
        return self.get_val(key)

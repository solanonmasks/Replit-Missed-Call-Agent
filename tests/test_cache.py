
import unittest
from utils.cache import Cache
import time

class TestCache(unittest.TestCase):
    def setUp(self):
        self.cache = Cache(max_size=2, ttl=1)

    def test_cache_set_get(self):
        self.cache.set('key1', 'value1')
        self.assertEqual(self.cache.get('key1')[0], 'value1')

    def test_cache_expiration(self):
        self.cache.set('key1', 'value1')
        time.sleep(1.1)  # Wait for TTL to expire
        self.assertIsNone(self.cache.get('key1'))

    def test_cache_max_size(self):
        self.cache.set('key1', 'value1')
        self.cache.set('key2', 'value2')
        self.cache.set('key3', 'value3')
        self.assertIsNone(self.cache.get('key1'))

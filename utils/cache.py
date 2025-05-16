
from functools import wraps
import time
from collections import OrderedDict

class Cache:
    def __init__(self, max_size=1000, ttl=300):  # 5 minutes TTL
        self.max_size = max_size
        self.ttl = ttl
        self.cache = OrderedDict()
        
    def get(self, key):
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp <= self.ttl:
                self.cache.move_to_end(key)
                return value
            else:
                del self.cache[key]
        return None
        
    def set(self, key, value):
        self.cache[key] = (value, time.time())
        self.cache.move_to_end(key)
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

cache = Cache()

def cached(ttl=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            key = f"{f.__name__}:{str(args)}:{str(kwargs)}"
            result = cache.get(key)
            if result is not None:
                return result
            result = f(*args, **kwargs)
            cache.set(key, result)
            return result
        return decorated_function
    return decorator

from datetime import datetime, timedelta
from collections import defaultdict
import threading

class Stats:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self.calls = defaultdict(int)
        self.errors = defaultdict(int)
        self.last_reset = datetime.now()

    def record_call(self, endpoint):
        with self._lock:
            self.calls[endpoint] += 1

    def record_error(self, endpoint):
        with self._lock:
            self.errors[endpoint] += 1

    def get_stats(self):
        with self._lock:
            return {
                'calls': dict(self.calls),
                'errors': dict(self.errors),
                'uptime': str(datetime.now() - self.last_reset)
            }

    def reset(self):
        with self._lock:
            self.calls.clear()
            self.errors.clear()
            self.last_reset = datetime.now()
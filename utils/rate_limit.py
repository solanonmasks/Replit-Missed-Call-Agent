from flask import request, jsonify
from functools import wraps
import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, calls=100, per=60):
        self.calls = calls  # Number of calls allowed
        self.per = per     # Time period in seconds
        self.tokens = defaultdict(list)  # Store timestamps for each IP

    def is_allowed(self, ip):
        now = time.time()
        self.tokens[ip] = [t for t in self.tokens[ip] if t > now - self.per]
        
        if len(self.tokens[ip]) >= self.calls:
            return False
            
        self.tokens[ip].append(now)
        return True

limiter = RateLimiter()

def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip = request.remote_addr
        if not limiter.is_allowed(ip):
            return jsonify({"error": "Rate limit exceeded"}), 429
        return f(*args, **kwargs)
    return decorated_function
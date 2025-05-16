from functools import wraps
from flask import session, redirect, url_for
from config import Config

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

def verify_admin_password(password):
    return password == Config.ADMIN_PASSWORD
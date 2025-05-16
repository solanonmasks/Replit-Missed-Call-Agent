
import os
from typing import Dict, Any

class Config:
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_FROM_NUMBER = os.getenv('TWILIO_FROM_NUMBER')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'default-secret-key')
    DEBUG = False
    PORT = 81
    HOST = '0.0.0.0'

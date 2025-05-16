
from flask import Flask, request, Response, json, session, jsonify, render_template
from routes.admin import admin_bp
from config import Config
from services.twilio_service import TwilioService
from services.openai_service import OpenAIService
from utils.error_handler import handle_errors
from utils.rate_limit import rate_limit
from utils.validation import validate_request
from utils.cache import cached
import logging
from time import time

from flask import Flask, request, Response, json, session, jsonify, render_template, make_response
app = Flask(__name__)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.before_request
def log_request():
    request.start_time = time()
    logger.info(f"Incoming {request.method} request to {request.path}")

@app.after_request
def log_response(response):
    duration = time() - request.start_time
    logger.info(f"Request completed in {duration:.2f}s with status {response.status_code}")
    return response
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

app.register_blueprint(admin_bp)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

twilio_service = TwilioService()
openai_service = OpenAIService()

from utils.stats import Stats

stats_tracker = Stats()

@app.route("/", methods=["GET"])
@handle_errors
def home():
    logger.info("Accessing home endpoint")
    stats_tracker.record_call('home')
    return "Server is live!"

@app.route("/handle-call", methods=["POST"])
def make_call():
    try:
        to_number = "+15555555555"  # Default test number
        from_number = Config.TWILIO_FROM_NUMBER
        
        call_sid = twilio_service.make_call(to_number, from_number)
        if call_sid:
            return jsonify({"status": "success", "call_sid": call_sid})
        return jsonify({"error": "Call failed"}), 500
    except Exception as e:
        logger.error(f"Call error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/chat", methods=["POST"])
@handle_errors
@rate_limit
@validate_request('prompt')
@cached(ttl=300)  # Cache responses for 5 minutes
def chat():
    data = request.json    
    logger.info("Generating chat response")
    response = openai_service.generate_response(data.get('prompt'))
    return {"response": response}

if __name__ == "__main__":
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=app.config['DEBUG']
    )

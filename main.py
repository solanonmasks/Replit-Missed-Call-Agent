
from flask import Flask, request, Response, json, session, jsonify, render_template
from routes.admin import admin_bp
from config import Config
from services.twilio_service import TwilioService
from services.openai_service import OpenAIService
from utils.error_handler import handle_errors
import logging

app = Flask(__name__)
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

@app.route("/call", methods=["POST"])
@handle_errors
def make_call():
    data = request.json
    if not data or not data.get('to_number') or not data.get('from_number'):
        return jsonify({"error": "Missing required parameters"}), 400
    
    logger.info(f"Making call to {data.get('to_number')}")
    call_sid = twilio_service.make_call(
        data.get('to_number'),
        data.get('from_number')
    )
    return {"call_sid": call_sid}

@app.route("/chat", methods=["POST"])
@handle_errors
def chat():
    data = request.json
    if not data or not data.get('prompt'):
        return jsonify({"error": "Missing prompt parameter"}), 400
        
    logger.info("Generating chat response")
    response = openai_service.generate_response(data.get('prompt'))
    return {"response": response}

if __name__ == "__main__":
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=app.config['DEBUG']
    )

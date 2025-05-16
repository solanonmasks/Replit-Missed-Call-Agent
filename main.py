
from flask import Flask, request, Response, json, session
from config import Config
from services.twilio_service import TwilioService
from services.openai_service import OpenAIService

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

twilio_service = TwilioService()
openai_service = OpenAIService()

@app.route("/", methods=["GET"])
def home():
    return "Server is live!"

@app.route("/call", methods=["POST"])
def make_call():
    data = request.json
    call_sid = twilio_service.make_call(
        data.get('to_number'),
        data.get('from_number')
    )
    return {"call_sid": call_sid}

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    response = openai_service.generate_response(data.get('prompt'))
    return {"response": response}

if __name__ == "__main__":
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=app.config['DEBUG']
    )

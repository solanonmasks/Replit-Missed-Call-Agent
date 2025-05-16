from flask import Flask, request, Response
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Dial
import os

app = Flask(__name__)

# Replace these with your actual Twilio credentials
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
FORWARD_TO_NUMBER = os.environ.get("FORWARD_TO_NUMBER")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

@app.route("/", methods=["GET"])
def home():
    return "Server is live!"

@app.route("/handle-call", methods=["POST"])
def handle_call():
    response = VoiceResponse()
    dial = Dial(action="/handle-call-result", timeout=20)
    dial.number(FORWARD_TO_NUMBER)  # Use environment variable
    response.append(dial)
    return Response(str(response), mimetype="text/xml")


@app.route("/handle-call-result", methods=["POST"])
def handle_call_result():
    try:
        call_status = request.form.get("DialCallStatus")
        from_number = request.form.get("From")

        if call_status in ["no-answer", "busy", "failed"] and TWILIO_PHONE_NUMBER and from_number:
            client.messages.create(
                body="Hey! Sorry we missed your call. What can we help you with?",
                from_=TWILIO_PHONE_NUMBER,
                to=from_number
            )
        return Response("", status=200)
    except Exception as e:
        print(f"Error in handle_call_result: {str(e)}")
        return Response("", status=200)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=81)

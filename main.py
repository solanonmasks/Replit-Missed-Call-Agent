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

def format_phone_number(number):
    if not number:
        return None
    # Remove any spaces or special characters
    cleaned = ''.join(filter(str.isdigit, number))
    # Add + and country code 1 if not present
    if not cleaned.startswith('1'):
        cleaned = '1' + cleaned
    return '+' + cleaned

# Format phone numbers
TWILIO_PHONE_NUMBER = format_phone_number(TWILIO_PHONE_NUMBER)
FORWARD_TO_NUMBER = format_phone_number(FORWARD_TO_NUMBER)

# Verify Twilio credentials are present
if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, FORWARD_TO_NUMBER]):
    print("ERROR: Missing Twilio credentials!")
    print(f"TWILIO_ACCOUNT_SID present: {bool(TWILIO_ACCOUNT_SID)}")
    print(f"TWILIO_AUTH_TOKEN present: {bool(TWILIO_AUTH_TOKEN)}")
    print(f"TWILIO_PHONE_NUMBER: {TWILIO_PHONE_NUMBER}")
    print(f"FORWARD_TO_NUMBER: {FORWARD_TO_NUMBER}")

# Test Twilio client
try:
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    print("Successfully initialized Twilio client")
except Exception as e:
    print(f"Failed to initialize Twilio client: {str(e)}")

@app.route("/", methods=["GET"])
def home():
    return "Server is live!"

@app.route("/handle-call", methods=["POST"])
def handle_call():
    try:
        print("Received call request")
        print(f"Call From: {request.form.get('From')}")
        print(f"Forwarding to: {FORWARD_TO_NUMBER}")
        
        if not FORWARD_TO_NUMBER or not FORWARD_TO_NUMBER.startswith('+'):
            raise ValueError(f"Invalid forward number format: {FORWARD_TO_NUMBER}")
            
        response = VoiceResponse()
        response.say("Please hold while we connect your call.")
        dial = Dial(action="/handle-call-result", timeout=30, hangupOnStar=True)
        dial.number(FORWARD_TO_NUMBER)
        response.append(dial)
        
        twiml = str(response)
        print(f"Generated TwiML: {twiml}")
        return Response(twiml, mimetype="text/xml")
    except Exception as e:
        print(f"Error in handle_call: {str(e)}")
        error_response = VoiceResponse()
        error_response.say("We're sorry, but there was an error processing your call.")
        return Response(str(error_response), mimetype="text/xml")


@app.route("/handle-call-result", methods=["POST"])
def handle_call_result():
    try:
        call_status = request.form.get("DialCallStatus")
        from_number = request.form.get("From")
        recording_url = request.form.get("RecordingUrl")
        call_duration = int(request.form.get("DialCallDuration", "0"))
        
        print(f"Call Status: {call_status}")
        print(f"From Number: {from_number}")
        print(f"Recording URL: {recording_url}")
        print(f"Call Duration: {call_duration} seconds")
        print(f"Twilio Phone: {TWILIO_PHONE_NUMBER}")

        # Consider it a missed call if duration is 0 or very short
        if call_duration < 3:  # Less than 3 seconds is probably a missed call
            call_status = "no-answer"

        if TWILIO_PHONE_NUMBER and FORWARD_TO_NUMBER:
            try:
                message_body = None
                timestamp = request.form.get("Timestamp", "Unknown time")
                
                if call_status == "completed" and recording_url:
                    message_body = f"Missed call with voicemail from {from_number} at {timestamp}\nVoicemail: {recording_url}"
                elif call_status in ["no-answer", "busy", "failed"] or call_duration < 3:
                    message_body = f"Missed call from {from_number} at {timestamp}"
                
                if message_body:
                    message = client.messages.create(
                        body=message_body,
                        from_=TWILIO_PHONE_NUMBER,
                        to=FORWARD_TO_NUMBER  # Send to plumber instead of caller
                    )
                    print(f"Notification sent to plumber: {message.sid}")
            except Exception as sms_error:
                print(f"SMS sending failed: {str(sms_error)}")
        return Response("", status=200)
    except Exception as e:
        print(f"Error in handle_call_result: {str(e)}")
        return Response("", status=200)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=81)

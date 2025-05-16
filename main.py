
from flask import Flask, request, Response
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
import os
import openai

app = Flask(__name__)

# Twilio credentials
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
FORWARD_TO_NUMBER = os.environ.get("FORWARD_TO_NUMBER")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Verify credentials
if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, FORWARD_TO_NUMBER]):
    print("ERROR: Missing required Twilio credentials!")
    print(f"ACCOUNT_SID: {'Present' if TWILIO_ACCOUNT_SID else 'Missing'}")
    print(f"AUTH_TOKEN: {'Present' if TWILIO_AUTH_TOKEN else 'Missing'}")
    print(f"PHONE_NUMBER: {'Present' if TWILIO_PHONE_NUMBER else 'Missing'}")
    print(f"FORWARD_NUMBER: {'Present' if FORWARD_TO_NUMBER else 'Missing'}")

openai.api_key = OPENAI_API_KEY

def format_phone_number(number):
    if not number:
        return None
    cleaned = ''.join(filter(str.isdigit, number))
    if not cleaned.startswith('1'):
        cleaned = '1' + cleaned
    return '+' + cleaned

TWILIO_PHONE_NUMBER = format_phone_number(TWILIO_PHONE_NUMBER)
FORWARD_TO_NUMBER = format_phone_number(FORWARD_TO_NUMBER)

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def get_gpt_advice(issue):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful plumbing assistant. Provide brief, practical advice for common plumbing issues."},
                {"role": "user", "content": f"What's the immediate solution for: {issue}"}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"GPT error: {str(e)}")
        return "I apologize, but I couldn't generate specific advice at the moment."

customer_states = {}  # Store customer interaction states

@app.route("/", methods=["GET"])
def home():
    return "Server is live!"

@app.route("/handle-call", methods=["POST"])
def handle_call():
    response = VoiceResponse()
    # Try to forward to plumber first
    dial = response.dial(timeout=15, action='/handle-no-answer')
    dial.number(FORWARD_TO_NUMBER)
    return str(response)

@app.route("/handle-no-answer", methods=["POST"])
def handle_no_answer():
    dial_status = request.form.get("DialCallStatus")
    from_number = request.form.get("From")
    
    response = VoiceResponse()
    print(f"handle_no_answer called with status: {dial_status}")
    print(f"Request form data: {request.form}")
    
    # Test SMS immediately
    try:
        print(f"\nAttempting to send test SMS:")
        print(f"From: {TWILIO_PHONE_NUMBER}")
        print(f"To: {from_number}")
        
        test_message = client.messages.create(
            body="Test message from FlowRite Plumbing",
            from_=TWILIO_PHONE_NUMBER,
            to=from_number
        )
        print(f"Test SMS sent with SID: {test_message.sid}")
    except Exception as e:
        print(f"Test SMS failed with error: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        return str(VoiceResponse())  # Return empty response on error
    if dial_status in ["no-answer", "busy", "failed"]:
        print(f"Call not answered. Status: {dial_status}")
        print(f"Customer number: {from_number}")
        print(f"Twilio number: {TWILIO_PHONE_NUMBER}")
        print(f"Plumber number: {FORWARD_TO_NUMBER}")
        response.say("Sorry, we couldn't reach our plumber. We'll send you a text message shortly to collect more information.")
        # Send initial SMS
        try:
            message = client.messages.create(
                body="Hi! This is FlowRite Plumbing. Could you please tell us your name?",
                from_=TWILIO_PHONE_NUMBER,
                to=from_number
            )
            print(f"SMS sent successfully with SID: {message.sid}")
            customer_states[from_number] = {"stage": "waiting_for_name"}
        except Exception as e:
            print(f"Error sending SMS: {str(e)}")
            print(f"TWILIO_PHONE_NUMBER: {TWILIO_PHONE_NUMBER}")
            print(f"Customer number: {from_number}")
    
    response.hangup()
    return str(response)

@app.route("/status", methods=["POST"])
def handle_status():
    return Response("", status=200)

@app.route("/sms", methods=["POST"])
def handle_sms():
    from_number = request.form.get("From")
    message_body = request.form.get("Body", "").strip()
    
    if from_number not in customer_states:
        customer_states[from_number] = {"stage": "waiting_for_name"}
    
    state = customer_states[from_number]
    
    try:
        if state["stage"] == "waiting_for_name":
            state["name"] = message_body
            state["stage"] = "waiting_for_issue"
            response = "Thanks! Could you briefly describe your plumbing issue?"
            
        elif state["stage"] == "waiting_for_issue":
            state["issue"] = message_body
            advice = get_gpt_advice(message_body)
            
            # Send info to plumber
            plumber_message = client.messages.create(
                body=f"New plumbing request:\nName: {state['name']}\nPhone: {from_number}\nIssue: {state['issue']}",
                from_=TWILIO_PHONE_NUMBER,
                to=FORWARD_TO_NUMBER
            )
            
            # Send advice to customer
            response = f"Thanks for providing the details! Here's some immediate advice: {advice}\n\nOur plumber will contact you shortly."
            del customer_states[from_number]  # Clear the state
        
        # Send response back to customer
        message = client.messages.create(
            body=response,
            from_=TWILIO_PHONE_NUMBER,
            to=from_number
        )
        
    except Exception as e:
        print(f"Error in SMS handling: {str(e)}")
        
    return Response("", status=200)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=81)

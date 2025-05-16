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

# Initialize OpenAI client with API key from environment
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
print(f"OpenAI client initialized with API key starting with: {OPENAI_API_KEY[:5]}..." if OPENAI_API_KEY else "No OpenAI API key found!")

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
        print(f"\n=== Starting GPT Request ===")
        print(f"Issue: {issue}")
        print(f"API Key status: {'Present' if OPENAI_API_KEY else 'Missing'}")
        print(f"API Key length: {len(OPENAI_API_KEY) if OPENAI_API_KEY else 0}")

        if not OPENAI_API_KEY:
            raise ValueError("OpenAI API key is missing")

        # Validate API key format
        if not OPENAI_API_KEY.startswith('sk-'):
            raise ValueError("Invalid API key format - should start with 'sk-'")

        print(f"Calling OpenAI API with issue: {issue}")
        print(f"Using API key: {OPENAI_API_KEY[:5]}..." if OPENAI_API_KEY else "No API key!")

        # Test the API connection first
        print("Testing API connection...")
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful plumbing assistant."},
                {"role": "user", "content": f"What's a quick fix for this plumbing issue: {issue}"}
            ],
            max_tokens=150,
            temperature=0.7
        )

        # Access the response content correctly
        content = response.choices[0].message.content if response.choices else "No response generated"
        print(f"Got GPT response: {content}")
        return content
    except Exception as e:
        print(f"Detailed GPT error: {str(e)}")
        print(f"API Key present: {'Yes' if openai.api_key else 'No'}")
        return "I apologize, but I couldn't generate specific advice at the moment. Please try again."

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
    print("\n=== Handling No Answer ===")
    print(f"Dial Status: {dial_status}")
    print(f"From Number: {from_number}")
    print(f"Request Form Data: {request.form}")

    if dial_status != "answered":
        print("\n=== Sending Initial SMS ===")
        print(f"From (Twilio): {TWILIO_PHONE_NUMBER}")
        print(f"To (Customer): {from_number}")
        print(f"Forward Number (Plumber): {FORWARD_TO_NUMBER}")
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

@app.route("/test", methods=["GET"])
def test():
    return "SMS webhook is working!"

@app.route("/sms", methods=["POST"])
def handle_sms():
    print("\n=== SMS Webhook Hit ===")
    print(f"Request Method: {request.method}")
    print(f"Request Form: {request.form}")
    print(f"Request Headers: {request.headers}")

    from_number = request.form.get("From")
    message_body = request.form.get("Body", "").strip()

    if from_number not in customer_states:
        customer_states[from_number] = {"stage": "waiting_for_name"}

    state = customer_states[from_number]
    print(f"\n=== Handling SMS ===")
    print(f"From: {from_number}")
    print(f"Message: {message_body}")
    print(f"Current state: {state}")

    try:
        if state["stage"] == "waiting_for_name":
            state["name"] = message_body
            state["stage"] = "waiting_for_issue"
            response = "Thanks! Could you briefly describe your plumbing issue?"

        elif state["stage"] == "waiting_for_issue":
            state["issue"] = message_body
            state["stage"] = "waiting_for_consent"

            # Send info to plumber
            plumber_message = client.messages.create(
                body=f"New plumbing request:\nName: {state['name']}\nPhone: {from_number}\nIssue: {state['issue']}",
                from_=TWILIO_PHONE_NUMBER,
                to=FORWARD_TO_NUMBER
            )

            response = "Would you like some immediate AI-powered advice about your issue? Reply YES or NO."

        elif state["stage"] == "waiting_for_consent":
            if message_body.upper() == "YES":
                advice = get_gpt_advice(state["issue"])
                response = f"Here's some immediate advice: {advice}\n\nOur plumber will contact you shortly. Need more help? Just ask!"
                state["stage"] = "chatting"
            else:
                response = "Okay, no problem. Our plumber will contact you shortly."
                del customer_states[from_number]

        elif state["stage"] == "chatting":
            advice = get_gpt_advice(message_body)
            response = f"{advice}\n\nNeed more help? Just ask! Or type STOP to end the conversation."
            if message_body.upper() == "STOP":
                response = "Thanks for chatting! Our plumber will be in touch soon."
                del customer_states[from_number]

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
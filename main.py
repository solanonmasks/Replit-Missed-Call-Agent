from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
import os
import openai

app = Flask(__name__)

@app.route("/")
def index():
    return "Plumbing Service API is running!"

# Initialize Twilio client
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
FORWARD_TO_NUMBER = os.environ.get("FORWARD_TO_NUMBER")

print("Twilio Configuration:")
print(f"Account SID exists: {bool(TWILIO_ACCOUNT_SID)}")
print(f"Auth Token exists: {bool(TWILIO_AUTH_TOKEN)}")
print(f"Phone Number exists: {bool(TWILIO_PHONE_NUMBER)}")
print(f"Forward Number exists: {bool(FORWARD_TO_NUMBER)}")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Initialize OpenAI
openai.api_key = os.environ.get("OPENAI_API_KEY")

customer_states = {}  # Store customer interaction states

@app.route("/test-sms")
def test_sms():
    try:
        message = client.messages.create(
            body="Test message from your plumbing service",
            from_=TWILIO_PHONE_NUMBER,
            to=FORWARD_TO_NUMBER
        )
        return f"Test SMS sent! Message SID: {message.sid}"
    except Exception as e:
        return f"Error sending SMS: {str(e)}"

@app.route("/sms", methods=["POST"])
def handle_sms():
    from_number = request.form.get("From")
    message_body = request.form.get("Body", "").strip()
    print(f"Received message from {from_number}: {message_body}")

    # Forward every message to plumber first
    try:
        client.messages.create(
            body=f"Message from {from_number}:\n{message_body}",
            from_=TWILIO_PHONE_NUMBER,
            to=FORWARD_TO_NUMBER
        )
    except Exception as e:
        print(f"Error forwarding to plumber: {str(e)}")

    # Debug OpenAI key
    print(f"OpenAI key exists: {bool(openai.api_key)}")

    # Then handle customer conversation
    if from_number not in customer_states:
        customer_states[from_number] = {"stage": "waiting_for_name"}
        response = "Hi this is FloWrite Plumbing. Could you please tell us your name?"
        try:
            message = client.messages.create(
                body=response,
                from_=TWILIO_PHONE_NUMBER,
                to=from_number
            )
        except Exception as e:
            print(f"Error sending SMS: {str(e)}")
        return Response("", status=200)

    state = customer_states[from_number]

    try:
        if state["stage"] == "waiting_for_name":
            state["name"] = message_body
            state["stage"] = "waiting_for_issue"
            response = "Thanks! Could you briefly describe your plumbing issue?"

        elif state["stage"] == "waiting_for_issue":
            state["issue"] = message_body
            state["stage"] = "chatting"

            # Send info to plumber
            plumber_message = client.messages.create(
                body=f"New plumbing request:\nName: {state['name']}\nPhone: {from_number}\nIssue: {state['issue']}",
                from_=TWILIO_PHONE_NUMBER,
                to=FORWARD_TO_NUMBER
            )

            # Send confirmation to customer
            response = (
                f"Thanks {state['name']}, we've received your request and the plumber will contact you as soon as possible.\n\n"
                "Feel free to ask any questions while you wait!"
            )

        elif state["stage"] == "chatting":
            if message_body.upper() == "STOP":
                response = "Thanks for chatting! Our plumber will be in touch soon."
                del customer_states[from_number]
            else:
                completion = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are FloWrite Plumbing's AI assistant. You specialize in providing helpful, accurate plumbing advice. Focus on common household plumbing issues, maintenance tips, and emergency guidance. Be professional but friendly, and always emphasize safety. If an issue sounds serious, remind them that a professional assessment is recommended."},
                        {"role": "user", "content": message_body}
                    ]
                )
                response = completion.choices[0].message.content + "\n\nNeed more help? Just ask! Or type STOP to end the conversation."

        # Send response back to customer
        message = client.messages.create(
            body=response,
            from_=TWILIO_PHONE_NUMBER,
            to=from_number
        )

    except Exception as e:
        print(f"Error in SMS handling: {str(e)}")

    return Response("", status=200)

@app.route("/handle-call", methods=["POST"])
def handle_call():
    response = VoiceResponse()
    dial = response.dial(timeout=15, action="/call-status")
    dial.number(FORWARD_TO_NUMBER)
    return str(response)

@app.route("/call-status", methods=["POST"])
def call_status():
    caller = request.values.get('From')
    duration = request.values.get('DialCallDuration')
    status = request.values.get('DialCallStatus')
    
    if status in ['no-answer', 'busy', 'failed'] or (status == 'completed' and duration and int(duration) < 10):
        try:
            client.messages.create(
                body="Hi this is FloWrite Plumbing. Could you please tell us your name?",
                from_=TWILIO_PHONE_NUMBER,
                to=caller
            )
            customer_states[caller] = {"stage": "waiting_for_name"}
            client.messages.create(
                body=f"Missed call or short call from: {caller}",
                from_=TWILIO_PHONE_NUMBER,
                to=FORWARD_TO_NUMBER
            )
        except Exception as e:
            print(f"Error in call handling: {str(e)}")
    
    response = VoiceResponse()
    return str(response)

if __name__ == "__main__":
    try:
        app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'default-dev-key')
        app.run(host='0.0.0.0', port=81, debug=False)
    except Exception as e:
        print(f"Application error: {str(e)}")
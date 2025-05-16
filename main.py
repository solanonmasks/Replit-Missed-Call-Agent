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

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Initialize OpenAI
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Store customer interaction states
customer_states = {}

@app.route("/sms", methods=["POST"])
def handle_sms():
    from_number = request.form.get("From")
    message_body = request.form.get("Body", "").strip()

    # Forward all messages to plumber
    try:
        client.messages.create(
            body=f"Message from {from_number}:\n{message_body}",
            from_=TWILIO_PHONE_NUMBER,
            to=FORWARD_TO_NUMBER
        )
    except Exception as e:
        print(f"Error forwarding to plumber: {str(e)}")

    try:
        if from_number not in customer_states:
            customer_states[from_number] = {"stage": "waiting_for_name"}
            response = "Hi this is FloWrite Plumbing. Could you please tell us your name?"
        else:
            state = customer_states[from_number]

            if state["stage"] == "waiting_for_name":
                state["name"] = message_body
                state["stage"] = "waiting_for_issue"
                response = "Thanks! Could you briefly describe your plumbing issue?"

            elif state["stage"] == "waiting_for_issue":
                state["issue"] = message_body
                state["stage"] = "chatting"

                # Send to plumber
                plumber_message = f"New plumbing request:\nName: {state['name']}\nPhone: {from_number}\nIssue: {state['issue']}"
                client.messages.create(
                    body=plumber_message,
                    from_=TWILIO_PHONE_NUMBER,
                    to=FORWARD_TO_NUMBER
                )

                # Confirm to customer
                response = (
                    f"Thanks {state['name']}, we've received your request and the plumber will contact you as soon as possible.\n\n"
                    "Feel free to ask any questions while you wait!"
                )

            elif state["stage"] == "chatting":
                # Use OpenAI for chat responses
                completion = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are FloWrite Plumbing's AI assistant. Provide helpful plumbing advice while being professional and friendly. Focus on safety and common issues. For serious issues, recommend professional assessment."},
                        {"role": "user", "content": message_body}
                    ]
                )
                response = completion.choices[0].message.content

        # Send response to customer
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
                body=f"Missed call from: {caller}",
                from_=TWILIO_PHONE_NUMBER,
                to=FORWARD_TO_NUMBER
            )
        except Exception as e:
            print(f"Error handling missed call: {str(e)}")

    return str(VoiceResponse())

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=81)
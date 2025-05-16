from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
import os
import openai

app = Flask(__name__)

# Initialize Twilio client
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
FORWARD_TO_NUMBER = os.environ.get("FORWARD_TO_NUMBER")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Initialize OpenAI
openai.api_key = os.environ.get("OPENAI_API_KEY")

customer_states = {}  # Store customer interaction states

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
            state["stage"] = "chatting"

            # Send info to plumber
            plumber_message = client.messages.create(
                body=f"New plumbing request:\nName: {state['name']}\nPhone: {from_number}\nIssue: {state['issue']}",
                from_=TWILIO_PHONE_NUMBER,
                to=FORWARD_TO_NUMBER
            )

            # Send confirmation to customer
            response = (
                f"Thanks {state['name']}, we've received your request and our plumber will contact you soon.\n\n"
                "Feel free to ask any questions while you wait! Type STOP to end the conversation."
            )

        elif state["stage"] == "chatting":
            if message_body.upper() == "STOP":
                response = "Thanks for chatting! Our plumber will be in touch soon."
                del customer_states[from_number]
            else:
                completion = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a helpful plumbing assistant. Provide useful advice while customers wait for the plumber."},
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
    dial = response.dial(timeout=15)
    dial.number(FORWARD_TO_NUMBER)
    return str(response)

if __name__ == "__main__":
    try:
        app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'default-dev-key')
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        print(f"Application error: {str(e)}")
from flask import Flask, request, Response
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Dial, Gather
import os
import openai

app = Flask(__name__)

# Twilio credentials
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
FORWARD_TO_NUMBER = os.environ.get("FORWARD_TO_NUMBER")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

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

@app.route("/", methods=["GET"])
def home():
    return "Server is live!"

@app.route("/handle-call", methods=["POST"])
def handle_call():
    response = VoiceResponse()
    response.say("Welcome to FlowRite Plumbing. Please tell us your name after the beep.")
    response.gather(
        input='speech',
        action='/handle-name',
        method='POST',
        timeout=5,
        speechTimeout='auto'
    )
    return Response(str(response), mimetype='text/xml')

@app.route("/handle-name", methods=["POST"])
def handle_name():
    name = request.form.get("SpeechResult", "").strip()
    response = VoiceResponse()

    gather = Gather(input='speech', action='/handle-issue', method='POST', timeout=10, speechTimeout='auto')
    gather.say(f"Hi {name}, please briefly describe your plumbing issue.")
    response.append(gather)

    # Store name in session
    response.set_cookie('customer_name', name)
    return Response(str(response), mimetype='text/xml')

@app.route("/handle-issue", methods=["POST"])
def handle_issue():
    issue = request.form.get("SpeechResult", "").strip()
    name = request.cookies.get('customer_name', 'Customer')

    # Get GPT advice
    advice = get_gpt_advice(issue)

    response = VoiceResponse()
    response.say(f"Thank you for explaining. Here's some immediate advice: {advice}")
    response.say("I'll now send your information to our plumber who will contact you shortly.")

    # Send info to plumber
    try:
        from_number = request.form.get("From")
        message = client.messages.create(
            body=f"New plumbing request:\nName: {name}\nPhone: {from_number}\nIssue: {issue}\nAI Advice Given: {advice}",
            from_=TWILIO_PHONE_NUMBER,
            to=FORWARD_TO_NUMBER
        )
        print(f"Message sent to plumber: {message.sid}")
    except Exception as e:
        print(f"Error sending message: {str(e)}")

    return Response(str(response), mimetype='text/xml')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=81)
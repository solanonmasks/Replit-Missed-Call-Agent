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
try:
    openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
    # Test the client immediately
    test_response = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Test message"}],
        max_tokens=10
    )
    print("OpenAI client test successful!")
    print(f"Test response: {test_response}")
except Exception as e:
    print(f"OpenAI initialization error: {str(e)}")
    print(f"API key type: {type(OPENAI_API_KEY)}")
    print(f"API key length: {len(OPENAI_API_KEY) if OPENAI_API_KEY else 0}")

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

def get_gpt_advice(message, state=None):
    try:
        print(f"\n=== Starting GPT Request ===")
        print(f"Message: {message}")
        
        if not OPENAI_API_KEY:
            raise ValueError("OpenAI API key is missing")

        # Build conversation history with better context
        messages = [
            {"role": "system", "content": f"""You are Sarah, the virtual assistant for FlowRite Plumbing. You're knowledgeable, empathetic, and practical. You maintain a natural, conversational tone while being professional.

            Customer Context:
            Name: {state.get('name', 'the customer') if state else 'the customer'}
            Current Issue: {state.get('issue', 'unknown') if state else 'unknown'}

            Conversation Guidelines:
            - Be conversational and natural, avoid repetitive or robotic responses
            - Reference previous parts of the conversation when relevant
            - Ask clarifying questions when needed
            - Show expertise but remain approachable
            - Acknowledge customer concerns with empathy

            Your Purpose:
            1. Bridge communication while our plumber reviews their case
            2. Provide expert guidance without overstepping
            3. Keep customers informed and reassured
            4. Help assess urgency and safety

            Response Style:
            - Use conversational language ("I understand that..." instead of "Issue acknowledged")
            - Personalize responses using their name and issue details
            - Avoid repetitive phrasings and generic responses
            - Show you're actively listening by referencing their specific concerns

            Emergency Situations (advise immediate action):
            - Gas smell
            - Flooding/major water leaks
            - Sewage backups
            - No water service
            - Risk of pipe freezing

            For emergencies, emphasize:
            "This situation requires immediate attention. While waiting for our callback, you should [specific safety action]. If you can't reach us immediately and this is an emergency, you may need to contact emergency services."

            Standard Response Structure:
            1. Acknowledge the issue
            2. Provide safe temporary solutions (if applicable)
            3. Remind that a plumber will assess the situation
            4. Ask for relevant details if needed

            Maintain a professional, knowledgeable tone while being clear that our plumber will provide a proper assessment."""},
        ]

        # Build comprehensive conversation history
        if state:
            # Add previous messages from state if they exist
            if "conversation_history" in state:
                messages.extend(state["conversation_history"])
            else:
                state["conversation_history"] = []
            
            # Add current message with better context tracking
            current_message = {
                "role": "user",
                "content": message
            }
            messages.append(current_message)
            
            # Store both user messages and assistant responses
            if "conversation_history" not in state:
                state["conversation_history"] = []
            state["conversation_history"].append(current_message)
            
            # Limit conversation history to last 10 messages to maintain context without overflow
            if len(state["conversation_history"]) > 10:
                state["conversation_history"] = state["conversation_history"][-10:]
        else:
            messages.append({"role": "user", "content": message})

        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=messages,
            max_tokens=500,
            temperature=0.9,
            presence_penalty=0.6,
            frequency_penalty=0.6
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
            state["stage"] = "issue_received"

            # Send info to plumber
            plumber_message = client.messages.create(
                body=f"New plumbing request:\nName: {state['name']}\nPhone: {from_number}\nIssue: {state['issue']}",
                from_=TWILIO_PHONE_NUMBER,
                to=FORWARD_TO_NUMBER
            )

            response = (
                f"Thanks {state['name']}, we've received your request and our plumber will contact you as soon as possible. "
                "If you'd like some immediate DIY tips while you wait, just reply TIPS. "
                "Otherwise, we'll be in touch shortly!"
            )
            state["stage"] = "waiting_for_tips_request"

        elif state["stage"] == "waiting_for_tips_request":
            if message_body.upper() == "TIPS":
                advice = get_gpt_advice(state["issue"])
                response = f"Here are some temporary tips that might help: {advice}\n\nOur plumber will still contact you shortly. Need more tips? Just ask!"
                state["stage"] = "chatting"
            elif message_body.upper() == "STOP":
                response = "No problem! Our plumber will be in touch soon."
                del customer_states[from_number]
            else:
                response = "Our plumber will be in touch soon. If you'd like some DIY tips while you wait, just reply TIPS."

        elif state["stage"] == "chatting":
            advice = get_gpt_advice(message_body, state)
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
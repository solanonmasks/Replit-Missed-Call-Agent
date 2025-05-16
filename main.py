from flask import Flask, request, Response, json, session, redirect, url_for, flash
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
import os
import openai

app = Flask(__name__)

# Multi-business configuration
BUSINESS_CONFIG = {
    "+17786535845": {  # Twilio number as key
        "forward_to": "+16044423722",
        "business_name": "FlowRite Plumbing",
        "business_type": "plumber",  # plumber, electrician, handyman, etc.
        "twilio_sid": os.environ.get("TWILIO_ACCOUNT_SID"),
        "twilio_token": os.environ.get("TWILIO_AUTH_TOKEN"),
        "openai_key": os.environ.get("OPENAI_API_KEY")
    }
    # Add more businesses here
}

# Default credentials for testing
TWILIO_ACCOUNT_SID = BUSINESS_CONFIG[list(BUSINESS_CONFIG.keys())[0]]["twilio_sid"]
TWILIO_AUTH_TOKEN = BUSINESS_CONFIG[list(BUSINESS_CONFIG.keys())[0]]["twilio_token"]
TWILIO_PHONE_NUMBER = list(BUSINESS_CONFIG.keys())[0]
FORWARD_TO_NUMBER = BUSINESS_CONFIG[TWILIO_PHONE_NUMBER]["forward_to"]
OPENAI_API_KEY = BUSINESS_CONFIG[TWILIO_PHONE_NUMBER]["openai_key"]

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

        # Build conversation history with enhanced context and capabilities
        messages = [
            {"role": "system", "content": f"""You are a friendly, experienced {BUSINESS_CONFIG[TWILIO_PHONE_NUMBER]['business_type']} having a natural conversation. Speak casually but professionally, like you're talking to a neighbor. Your key traits:

            1. Never ask about information already provided
            2. Focus on being helpful, not gathering more details
            3. Give practical advice in everyday language
            4. If something is dangerous, be direct about it

            When responding:
            - Use natural phrases like "I hear you" or "That's definitely frustrating"
            - Skip formal assessments - just give helpful tips
            - If you need to explain something technical, use simple comparisons
            - Don't ask for more details to "pass to the plumber" - they already have the info

            Customer Profile:
            Name: {state.get('name', 'the customer') if state else 'the customer'}
            Issue: {state.get('issue', 'unknown') if state else 'unknown'}

            Remember:
            - The plumber already has the customer's contact info and issue details
            - Focus on being helpful while they wait
            - Keep the conversation natural and friendly
            - Modern plumbing technology and materials
            - Common failure points and prevention
            - Emergency vs non-emergency situations
            - Cost estimation factors

            Your Purpose:
            1. Bridge communication while our plumber reviews their case
            2. Provide expert guidance without overstepping
            3. Keep customers informed and reassured
            4. Help assess urgency and safety

            Emergency Situations:
            For serious issues (gas, flooding, sewage), immediately say:
            "Hey, this is serious - you should [specific safety action] right away. If you can't reach emergency services, call 911."

            Otherwise:
            - Give helpful tips in a friendly way
            - Use everyday language
            - Focus on what they can safely do while waiting
            - No need to gather more info - just be helpful

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

            # Maintain full conversation context with structured history
            if len(state["conversation_history"]) > 20:
                # Keep first 5 messages (context setting) and last 15 messages (recent context)
                state["conversation_history"] = (
                    state["conversation_history"][:5] + 
                    state["conversation_history"][-15:]
                )

            # Add conversation markers for better context awareness
            if len(state["conversation_history"]) > 1:
                current_message["content"] = f"Previous context: {state['conversation_history'][-1]['content']}\nNew message: {message}"
        else:
            messages.append({"role": "user", "content": message})

        response = openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=messages,
            max_tokens=1000,
            temperature=0.9,
            presence_penalty=0.7,
            frequency_penalty=0.7,
            top_p=1
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
    return """
    <html>
    <head>
        <title>Plumbing Business Management</title>
        <style>
            body { font-family: Arial; max-width: 600px; margin: 40px auto; padding: 20px; }
        </style>
    </head>
    <body>
        <h1>Plumbing Business Management</h1>
        <p>Welcome to our plumbing management system.</p>
    </body>
    </html>
    """

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

    call_status = request.form.get("CallStatus")
    dial_duration = int(request.form.get("DialCallDuration", "0"))

    if dial_status != "answered" or (call_status == "completed" and dial_duration < 10):
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
            # Clean and validate the name
            cleaned_name = message_body.strip()
            if len(cleaned_name) < 2 or len(cleaned_name) > 30:
                response = "Please provide a valid name between 2 and 30 characters."
            elif not any(c.isalpha() for c in cleaned_name):
                response = "Please provide a name containing letters."
            else:
                # Only use the first two words of the name to prevent long inappropriate phrases
                name_parts = cleaned_name.split()[:2]
                state["name"] = " ".join(name_parts)
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

            # Get initial AI response to the issue
            initial_advice = get_gpt_advice(message_body, state)
            response = (
                f"Thanks {state['name']}, we've received your request and our plumber will contact you soon.\n\n"
                f"{initial_advice}\n\n"
                "Feel free to ask any other questions while you wait! Type STOP anytime to end the conversation."
            )

        elif state["stage"] == "chatting":
            try:
                print(f"\n=== Getting GPT Advice ===")
                advice = get_gpt_advice(message_body, state)
                print(f"GPT Response: {advice}")
                
                response = f"{advice}\n\nNeed more help? Just ask! Or type STOP to end the conversation."
                if message_body.upper() == "STOP":
                    response = "Thanks for chatting! Our plumber will be in touch soon."
                    del customer_states[from_number]
            except Exception as e:
                print(f"Error getting GPT advice: {str(e)}")
                response = "I apologize, but I'm having trouble processing your message. Our plumber will contact you soon."

        # Send response back to customer
        message = client.messages.create(
            body=response,
            from_=TWILIO_PHONE_NUMBER,
            to=from_number
        )

    except Exception as e:
        print(f"Error in SMS handling: {str(e)}")

    return Response("", status=200)

import functools
from flask import redirect, url_for, session, request, flash

def admin_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == os.environ.get("ADMIN_PASSWORD", "admin123"):  # Default for testing
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        return "Invalid password"

    return """
        <form method="post">
            <h2>Admin Login</h2>
            <input type="password" name="password" placeholder="Enter admin password">
            <button type="submit">Login</button>
        </form>
    """



@app.route("/admin", methods=["GET"])
@admin_required
def admin_dashboard():
    # Get all subscriptions
    try:
        subscriptions = stripe.Subscription.list(limit=100)
    except:
        subscriptions = []

    stats = {number: {
        "business": config["business_name"],
        "active_chats": len([k for k,v in customer_states.items() 
                           if v.get("plumber_number") == number]),
        "forward_to": config["forward_to"],
        "total_conversations": len(customer_states),
        "active_conversations": len([k for k,v in customer_states.items() 
                                   if v.get("stage") == "chatting"])
    } for number, config in BUSINESS_CONFIG.items()}

    return f"""
    <h1>Plumber Management Dashboard</h1>
    <style>
        .stats {{ padding: 20px; background: #f5f5f5; border-radius: 5px; }}
        .actions {{ margin-top: 20px; }}
        button {{ padding: 10px; margin: 5px; }}
        .subscription-form {{ margin: 20px 0; padding: 20px; background: #fff; }}
    </style>
    <script src="https://js.stripe.com/v3/"></script>
    <div class="stats">
        <pre>{json.dumps(stats, indent=2)}</pre>
    </div>
    <div class="actions">
        <form action="/admin/add_plumber" method="post" style="margin-top: 20px;">
            <h3>Add New Plumber</h3>
            <input type="text" name="business_name" placeholder="Business Name" required><br>
            <input type="text" name="twilio_number" placeholder="Twilio Number" required><br>
            <input type="text" name="forward_to" placeholder="Forward Number" required><br>
            <button type="submit">Add Plumber</button>
        </form>
    </div>
    """

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_key")  # Default for testing

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=81)
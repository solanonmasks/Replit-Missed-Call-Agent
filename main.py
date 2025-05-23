from flask import Flask, request, Response, json, session, redirect, url_for, flash
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
import os
import openai

app = Flask(__name__)

# Multi-business configuration
BUSINESS_CONFIG = {}

def load_business_config():
    global BUSINESS_CONFIG
    # Shared credentials across all businesses
    shared_creds = {
        "twilio_sid": os.environ.get("TWILIO_ACCOUNT_SID"),
        "twilio_token": os.environ.get("TWILIO_AUTH_TOKEN"),
        "openai_key": os.environ.get("OPENAI_API_KEY")
    }
    
    # Load businesses from admin-configured storage
    # For now using a simple dictionary - can be replaced with database
    businesses = {
        "+17786535845": {
            "forward_to": "+16044423722",
            "business_name": "FlowRite Plumbing",
            "business_type": "plumber",
        }
    }
    
    # Combine shared credentials with business-specific config
    BUSINESS_CONFIG = {
        number: {**config, **shared_creds}
        for number, config in businesses.items()
    }

# Load initial configuration
load_business_config()

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

        # Get business type from config
        to_number = TWILIO_PHONE_NUMBER
        business_config = BUSINESS_CONFIG.get(to_number, BUSINESS_CONFIG[list(BUSINESS_CONFIG.keys())[0]])
        business_type = business_config.get('business_type', 'plumber')

        # Build conversation history with enhanced context and capabilities
        messages = [
            {"role": "system", "content": f"""You're a service professional assistant for {business_type} with 15 years of experience. Talk like a normal person - no corporate speak, just practical advice from experience. Keep it real and straight to the point.

            About the customer:
            Name: {state.get('name', 'the customer') if state else 'the customer'}
            Issue: {state.get('issue', 'unknown') if state else 'unknown'}
            Business Type: {business_config['business_type']}

            Key points:
            - Talk like you're chatting with a neighbor
            - Give quick, practical tips they can actually use
            - If it's dangerous, just tell them straight up
            - Don't repeat yourself unless they ask
            - Keep responses focused and helpful

            For emergencies:
            Just say "Whoa, hold up - you need to [safety action] right now. Call 911 if you can't get emergency services."

            Remember: Our plumber has their info and is checking the case. Just help them out while they wait."""},
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
            messages=messages + [{"role": "system", "content": "Keep responses clear and focused. Break up long explanations into digestible chunks."}],
            max_tokens=300,
            temperature=0.7,
            presence_penalty=0.6,
            frequency_penalty=0.6,
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
    return "Server is live!"

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "version": "1.0.0",
        "twilio_connected": bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN),
        "openai_connected": bool(OPENAI_API_KEY)
    })

@app.route("/handle-call", methods=["POST"])
def handle_call():
    response = VoiceResponse()
    # Get business info from incoming number
    to_number = request.form.get('To')
    business_config = BUSINESS_CONFIG.get(to_number, BUSINESS_CONFIG[TWILIO_PHONE_NUMBER])
    
    # Play custom greeting
    response.say(f"Thank you for calling {business_config['business_name']}. Please hold while we connect you with one of our specialists.")
    
    # Try to forward to plumber
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

    state = customer_states.get(from_number, {"stage": "waiting_for_name"})
    print(f"\n=== Handling SMS ===")
    print(f"From: {from_number}")
    print(f"Message: {message_body}")
    print(f"Current state: {state}")

    try:
        stage = state.get("stage", "waiting_for_name")
        if stage == "waiting_for_name":
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
                state["stage"] = "waiting_for_location"
                response = "Thanks! What area are you located in?"

        elif state["stage"] == "waiting_for_location":
            state["location"] = message_body
            state["stage"] = "waiting_for_issue"
            response = "Thanks! Could you briefly describe your plumbing issue?"

        elif state["stage"] == "waiting_for_issue":
            state["issue"] = message_body
            state["stage"] = "chatting"

            # First send acknowledgment and offer help
            response = (
                f"Thanks {state['name']}, I understand you're having an issue with {state['issue']}. "
                f"Our plumber will contact you soon.\n\n"
                "Would you like some help or advice while you wait?"
            )

            # Send this first message
            message = client.messages.create(
                body=response,
                from_=TWILIO_PHONE_NUMBER,
                to=from_number
            )

            # Then notify plumber
            try:
                plumber_message = client.messages.create(
                    body=f"New plumbing request:\nName: {state['name']}\nLocation: {state.get('location', 'Unknown')}\nPhone: {from_number}\nIssue: {state['issue']}",
                    from_=TWILIO_PHONE_NUMBER,
                    to=FORWARD_TO_NUMBER
                )
            except Exception as e:
                print(f"Error notifying plumber: {str(e)}")

            # Don't send another response since we already sent one
            return Response("", status=200)

            # Then notify plumber
            try:
                plumber_message = client.messages.create(
                    body=f"New plumbing request:\nName: {state['name']}\nLocation: {state.get('location', 'Unknown')}\nPhone: {from_number}\nIssue: {state['issue']}",
                    from_=TWILIO_PHONE_NUMBER,
                    to=FORWARD_TO_NUMBER
                )
            except Exception as e:
                print(f"Error notifying plumber: {str(e)}")

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

@app.route("/admin/add_business", methods=["POST"])
@admin_required
def add_business():
    data = request.form
    number = data.get('twilio_number')
    if number:
        businesses = BUSINESS_CONFIG.copy()
        businesses[number] = {
            "forward_to": data.get('forward_to'),
            "business_name": data.get('business_name'),
            "business_type": data.get('business_type'),
            "twilio_sid": os.environ.get("TWILIO_ACCOUNT_SID"),
            "twilio_token": os.environ.get("TWILIO_AUTH_TOKEN"),
            "openai_key": os.environ.get("OPENAI_API_KEY")
        }
        BUSINESS_CONFIG.update(businesses)
        flash('Business added successfully!')
    return redirect(url_for('admin_dashboard'))

@app.route("/admin", methods=["GET"])
@admin_required
def admin_dashboard():
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
    <h1>Business Management Dashboard</h1>
    <style>
        .stats {{ padding: 20px; background: #f5f5f5; border-radius: 5px; margin-bottom: 20px; }}
        .actions {{ margin-top: 20px; }}
        .form-group {{ margin: 10px 0; }}
        input {{ padding: 8px; margin: 5px 0; width: 300px; }}
        button {{ padding: 10px; margin: 5px; background: #4CAF50; color: white; border: none; cursor: pointer; }}
        select {{ padding: 8px; margin: 5px 0; width: 300px; }}
    </style>
    <div class="stats">
        <h2>Current Businesses</h2>
        <pre>{json.dumps(stats, indent=2)}</pre>
    </div>
    <div class="actions">
        <form action="/admin/add_business" method="post" style="margin-top: 20px;">
            <h3>Add New Business</h3>
            <div class="form-group">
                <input type="text" name="business_name" placeholder="Business Name" required>
            </div>
            <div class="form-group">
                <input type="text" name="twilio_number" placeholder="Twilio Number (format: +1XXXXXXXXXX)" required>
            </div>
            <div class="form-group">
                <input type="text" name="forward_to" placeholder="Forward to Number (format: +1XXXXXXXXXX)" required>
            </div>
            <div class="form-group">
                <select name="business_type" required>
                    <option value="plumber">Plumber</option>
                    <option value="electrician">Electrician</option>
                    <option value="handyman">Handyman</option>
                    <option value="hvac">HVAC</option>
                </select>
            </div>
            <button type="submit">Add Business</button>
        </form>
    </div>
    """

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_key")  # Default for testing

if __name__ == "__main__":
    from utils.logging_config import setup_logging
    setup_logging()
    app.run(host='0.0.0.0', port=81)
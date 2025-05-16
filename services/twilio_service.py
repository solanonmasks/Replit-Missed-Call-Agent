
from twilio.rest import Client
from config import Config

class TwilioService:
    def __init__(self):
        self.client = Client(
            Config.TWILIO_ACCOUNT_SID,
            Config.TWILIO_AUTH_TOKEN
        )

    def make_call(self, to_number, from_number):
        try:
            call = self.client.calls.create(
                to=to_number,
                from_=from_number,
                twiml='<Response><Say>This is a test call from your Twilio application</Say></Response>'
            )
            return call.sid
        except Exception as e:
            print(f"Call failed: {str(e)}")
            return None

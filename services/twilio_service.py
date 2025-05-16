
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
            if not self.client.account_sid or not self.client.auth_token:
                raise Exception("Twilio credentials not configured")
                
            call = self.client.calls.create(
                to=to_number,
                from_=from_number,
                url='http://demo.twilio.com/docs/voice.xml',
                twiml='<Response><Say>Hello from Twilio</Say></Response>'
            )
            return call.sid
        except Exception as e:
            raise Exception(f"Error making Twilio call: {str(e)}")

import sys
from app import config

from twilio.rest import Client

def make_call(target_number: str):
    client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)

    call = client.calls.create(
        to        = target_number,           # +55…
        from_     = config.TWILIO_PHONE_NUMBER,
        url       = f"{config.PUBLIC_BASE_URL}/voice",   # ← ESSENCIAL
        method    = "POST"                   # opcional, mas deixa explícito
    )
    print("Call initiated →", call.sid)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python dialer.py +5511XXXXXXXXX")
        sys.exit(1)
    make_call(sys.argv[1])
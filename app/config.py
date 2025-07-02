from dotenv import load_dotenv
import os, pathlib

# Carrega .env na raiz
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY")
ELEVEN_API_KEY      = os.getenv("ELEVEN_API_KEY")
VOICE_ID            = os.getenv("ELEVEN_VOICE_ID", "sol")

TWILIO_ACCOUNT_SID  = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
PUBLIC_BASE_URL     = os.getenv("PUBLIC_BASE_URL")  # https://... (ngrok ou domínio)

# URL exposto ao Twilio para TwiML & media‑stream
VOICE_WEBHOOK_URL = f"{PUBLIC_BASE_URL}/voice"
STREAM_WSS_URL    = f"wss://{PUBLIC_BASE_URL.lstrip('https://')}/twilio_stream"
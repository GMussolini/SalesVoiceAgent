from fastapi import APIRouter, Request, WebSocket
from twilio.twiml.voice_response import VoiceResponse, Start, Stream
import base64, asyncio

from app import config, speech, llm, agent_state

router = APIRouter()

@router.post("/voice")
async def voice_webhook(_: Request):
    """Twilio chama aqui no início da ligação (TwiML)."""
    resp = VoiceResponse()

    # Inicia media‑stream para WebSocket
    start = Start()
    start.stream(url=config.STREAM_WSS_URL)
    resp.append(start)

    # Pequena pausa (sinal de áudio vazia evita cortar início)
    resp.pause(length=1)

    # Saudação inicial
    resp.say("Olá! Aqui é o Renato da Musstins, tudo bem?", language="pt-BR")
    return str(resp)

@router.websocket("/twilio_stream")
async def twilio_stream(ws: WebSocket):
    await ws.accept()
    state = agent_state.init()
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("event") == "media":
                payload = base64.b64decode(msg["media"]["payload"])
                text = await speech.transcribe(payload)
                if not text:
                    continue
                state.user_turn(text)

                reply = await llm.generate_reply(state.history)
                state.agent_turn(reply)
                audio = await speech.synthesize(reply)
                await ws.send_bytes(audio)
            elif msg.get("event") == "closed":
                break
    finally:
        await ws.close()
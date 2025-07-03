from asyncio import subprocess
from fastapi import APIRouter, Request, WebSocket
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Start, Stream
import base64, asyncio
from twilio.twiml.voice_response import Connect

from app import config, speech, llm, agent_state

router = APIRouter()

@router.post("/voice")
async def voice_webhook(_: Request):
    """Twilio chama aqui no início da ligação (TwiML)."""
    resp = VoiceResponse()

    # Inicia media‑stream para WebSocket
    connect = Connect()
    connect.stream(url=config.STREAM_WSS_URL, track="inbound")
    resp.append(connect)

    # Pequena pausa (sinal de áudio vazia evita cortar início)
    resp.pause(length=1)

    # Saudação inicial
    resp.say("Olá! Aqui é o Giovanni da Musstins, tudo bem?", language="pt-BR")
    return Response(content=str(resp), media_type="application/xml")


@router.websocket("/twilio_stream")
async def twilio_stream(ws: WebSocket):
    await ws.accept()
    state = agent_state.init()
    print("✅ Conectado ao Twilio!")

    try:
        while True:
            msg = await ws.receive_json()

            match msg.get("event"):
                case "start":
                    print("🟢 Stream iniciado")
                case "stop":
                    print("🔴 Stream encerrado")
                    break
                case "media":
                    payload = base64.b64decode(msg["media"]["payload"])
                    wav = convert_mulaw_to_wav(payload)
                    text = await speech.transcribe(wav)

                    if not text.strip():
                        continue
                    
                    print(f"👤 {text}")
                    state.user_turn(text)

                    reply = await llm.generate_reply(state.history)
                    state.agent_turn(reply)
                    print(f"🤖 {reply}")

                    wav_reply = await speech.synthesize(reply)
                    mulaw = convert_wav_to_mulaw(wav_reply)

                    await ws.send_json({
                        "event": "media",
                        "media": { "payload": base64.b64encode(mulaw).decode() }
                    })
                case _:
                    print("Evento não tratado:", msg)

    except Exception as e:
        print(f"❌ Erro no WebSocket: {e}")
    finally:
        await ws.close()
        
def convert_wav_to_mulaw(wav_data: bytes) -> bytes:
    proc = subprocess.run(
        ["ffmpeg", "-i", "pipe:0", "-ar", "8000", "-ac", "1", "-f", "mulaw", "pipe:1"],
        input=wav_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=True
    )
    return proc.stdout

def convert_mulaw_to_wav(payload: bytes) -> bytes:
    proc = subprocess.run(
        ["ffmpeg", "-f", "mulaw", "-ar", "8000", "-ac", "1", "-i", "pipe:0", "-ar", "16000", "-ac", "1", "-f", "wav", "pipe:1"],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=True
    )
    return proc.stdout


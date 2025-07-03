from fastapi import APIRouter, Request, WebSocket
from fastapi.responses import Response
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
    resp.say("Olá! Aqui é o Giovanni da Musstins, tudo bem?", language="pt-BR")
    return Response(content=str(resp), media_type="application/xml")


@router.websocket("/twilio_stream")
async def twilio_stream(ws: WebSocket):
    await ws.accept()
    state = agent_state.init()
    
    try:
        while True:
            msg = await ws.receive_json()
            
            if msg.get("event") == "media":
                # Decodifica áudio do Twilio (formato mulaw, não wav)
                payload = base64.b64decode(msg["media"]["payload"])
                
                # PROBLEMA: Twilio envia áudio em formato mulaw, não WAV
                # Precisa converter antes de enviar para Whisper
                
                text = await speech.transcribe(payload)
                if not text.strip():
                    continue
                    
                print(f"User disse: {text}")  # Debug
                state.user_turn(text)

                reply = await llm.generate_reply(state.history)
                print(f"Agent responde: {reply}")  # Debug
                state.agent_turn(reply)
                
                # Sintetiza áudio
                audio_data = await speech.synthesize(reply)
                
                # PROBLEMA: Twilio espera dados em formato específico
                # Não pode simplesmente enviar bytes de áudio
                audio_b64 = base64.b64encode(audio_data).decode()
                
                # Envia no formato correto para Twilio
                await ws.send_json({
                    "event": "media",
                    "media": {
                        "payload": audio_b64
                    }
                })
                
            elif msg.get("event") == "start":
                print("Stream iniciado")
                
            elif msg.get("event") == "stop":
                print("Stream parado")
                break
                
    except Exception as e:
        print(f"Erro no WebSocket: {e}")
    finally:
        await ws.close()
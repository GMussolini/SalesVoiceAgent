import asyncio
import base64
import io
import audioop
from fastapi import APIRouter, Request, WebSocket
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Start, Stream, Connect

from app import config, speech, llm, agent_state

router = APIRouter()

@router.post("/voice")
async def voice_webhook(_: Request):
    """Twilio chama aqui no início da ligação (TwiML)."""
    resp = VoiceResponse()

    # Inicia media stream para WebSocket
    start = Start()
    start.stream(url=config.STREAM_WSS_URL)
    resp.append(start)

    # Saudação inicial
    resp.say("Olá! Aqui é o Giovanni da Musstins, tudo bem?", language="pt-BR")
    return Response(content=str(resp), media_type="application/xml")


@router.websocket("/twilio_stream")
async def twilio_stream(ws: WebSocket):
    await ws.accept()
    state = agent_state.init()
    print("✅ Conectado ao Twilio!")
    
    stream_sid = None

    try:
        while True:
            msg = await ws.receive_json()

            match msg.get("event"):
                case "start":
                    print("🟢 Stream iniciado")
                    stream_sid = msg["start"]["streamSid"]
                    print(f"Stream SID: {stream_sid}")
                    
                case "stop":
                    print("🔴 Stream encerrado")
                    break
                    
                case "media":
                    # Processa áudio recebido
                    payload = base64.b64decode(msg["media"]["payload"])
                    
                    # Converte mulaw para WAV
                    try:
                        wav_data = await convert_mulaw_to_wav_async(payload)
                        text = await speech.transcribe(wav_data)

                        if not text.strip():
                            continue
                        
                        print(f"👤 {text}")
                        state.user_turn(text)

                        # Gera resposta
                        reply = await llm.generate_reply(state.history)
                        state.agent_turn(reply)
                        print(f"🤖 {reply}")

                        # Sintetiza e envia resposta
                        wav_reply = await speech.synthesize(reply)
                        mulaw_reply = await convert_wav_to_mulaw_async(wav_reply)

                        # Envia áudio de volta para Twilio
                        await ws.send_json({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {
                                "payload": base64.b64encode(mulaw_reply).decode()
                            }
                        })
                        
                    except Exception as e:
                        print(f"Erro processando áudio: {e}")
                        continue
                        
                case _:
                    print(f"Evento não tratado: {msg}")

    except Exception as e:
        print(f"❌ Erro no WebSocket: {e}")
    finally:
        await ws.close()


async def convert_wav_to_mulaw_async(wav_data: bytes) -> bytes:
    """Converte WAV para mulaw usando ffmpeg de forma assíncrona"""
    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", 
            "-i", "pipe:0", 
            "-ar", "8000", 
            "-ac", "1", 
            "-f", "mulaw", 
            "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        
        stdout, _ = await process.communicate(input=wav_data)
        return stdout
        
    except Exception as e:
        print(f"Erro convertendo WAV para mulaw: {e}")
        return b""


async def convert_mulaw_to_wav_async(mulaw_data: bytes) -> bytes:
    """Converte mulaw para WAV usando ffmpeg de forma assíncrona"""
    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-f", "mulaw",
            "-ar", "8000", 
            "-ac", "1",
            "-i", "pipe:0",
            "-ar", "16000",
            "-ac", "1", 
            "-f", "wav",
            "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        
        stdout, _ = await process.communicate(input=mulaw_data)
        return stdout
        
    except Exception as e:
        print(f"Erro convertendo mulaw para WAV: {e}")
        return b""
import asyncio
import base64
import json
import logging
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Start
from typing import Dict, Any

from app import config, speech, llm, agent_state

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Store active connections
active_connections: Dict[str, WebSocket] = {}

@router.post("/voice")
async def voice_webhook(request: Request):
    """Twilio chama aqui no início da ligação (TwiML)."""
    try:
        # Log da requisição para debug
        body = await request.body()
        logger.info(f"Webhook recebido: {body.decode()}")
        
        resp = VoiceResponse()
        
        # Configurar media stream
        start = Start()
        # URL completa com protocolo wss://
        websocket_url = config.STREAM_WSS_URL
        if not websocket_url.startswith('wss://'):
            # Se não tem protocolo, adicionar
            if websocket_url.startswith('//'):
                websocket_url = f"wss:{websocket_url}"
            elif not websocket_url.startswith('ws'):
                websocket_url = f"wss://{websocket_url}"
        
        start.stream(url=websocket_url)
        resp.append(start)
        
        # Saudação inicial após configurar o stream
        resp.say("Olá! Aqui é o Giovanni da Musstins, tudo bem?", language="pt-BR")
        
        logger.info(f"TwiML gerado: {str(resp)}")
        return Response(content=str(resp), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Erro no webhook de voz: {e}")
        # Retorna TwiML simples em caso de erro
        resp = VoiceResponse()
        resp.say("Desculpe, houve um problema técnico.", language="pt-BR")
        return Response(content=str(resp), media_type="application/xml")


@router.websocket("/twilio_stream")
async def twilio_stream(websocket: WebSocket):
    await websocket.accept()
    
    call_sid = None
    stream_sid = None
    
    try:
        logger.info("✅ WebSocket conectado")
        state = agent_state.init()
        
        while True:
            try:
                # Receber mensagem do WebSocket
                message = await websocket.receive_text()
                data = json.loads(message)
                
                event = data.get("event")
                logger.info(f"Evento recebido: {event}")
                
                if event == "connected":
                    logger.info("🔗 WebSocket conectado ao Twilio")
                    
                elif event == "start":
                    stream_sid = data["start"]["streamSid"]
                    call_sid = data["start"]["callSid"]
                    logger.info(f"🟢 Stream iniciado - SID: {stream_sid}, Call: {call_sid}")
                    
                    # Armazenar conexão ativa
                    active_connections[stream_sid] = websocket
                    
                elif event == "media":
                    if not stream_sid:
                        logger.warning("Recebido media sem stream_sid")
                        continue
                        
                    # Processar áudio
                    await process_audio_message(websocket, data, state, stream_sid)
                    
                elif event == "stop":
                    logger.info("🔴 Stream encerrado")
                    if stream_sid in active_connections:
                        del active_connections[stream_sid]
                    break
                    
                else:
                    logger.info(f"Evento não tratado: {event}")
                    
            except json.JSONDecodeError as e:
                logger.error(f"Erro ao decodificar JSON: {e}")
                continue
                
            except Exception as e:
                logger.error(f"Erro processando mensagem: {e}")
                continue
                
    except WebSocketDisconnect:
        logger.info("🔌 WebSocket desconectado")
    except Exception as e:
        logger.error(f"❌ Erro no WebSocket: {e}")
    finally:
        if stream_sid and stream_sid in active_connections:
            del active_connections[stream_sid]
        try:
            await websocket.close()
        except:
            pass


async def process_audio_message(websocket: WebSocket, data: Dict[str, Any], state, stream_sid: str):
    """Processa mensagem de áudio do Twilio"""
    try:
        # Decodificar payload de áudio
        payload = base64.b64decode(data["media"]["payload"])
        
        # Converter mulaw para WAV
        wav_data = await convert_mulaw_to_wav_async(payload)
        if not wav_data:
            return
            
        # Transcrever áudio
        text = await speech.transcribe(wav_data)
        if not text or not text.strip():
            return
            
        logger.info(f"👤 Transcrição: {text}")
        state.user_turn(text)
        
        # Gerar resposta
        reply = await llm.generate_reply(state.history)
        if not reply:
            return
            
        state.agent_turn(reply)
        logger.info(f"🤖 Resposta: {reply}")
        
        # Sintetizar resposta
        wav_reply = await speech.synthesize(reply)
        if not wav_reply:
            return
            
        # Converter para mulaw
        mulaw_reply = await convert_wav_to_mulaw_async(wav_reply)
        if not mulaw_reply:
            return
            
        # Enviar áudio de volta
        media_message = {
            "event": "media",
            "streamSid": stream_sid,
            "media": {
                "payload": base64.b64encode(mulaw_reply).decode('utf-8')
            }
        }
        
        await websocket.send_text(json.dumps(media_message))
        logger.info("🎵 Áudio enviado de volta")
        
    except Exception as e:
        logger.error(f"Erro processando áudio: {e}")


async def convert_mulaw_to_wav_async(mulaw_data: bytes) -> bytes:
    """Converte mulaw para WAV usando ffmpeg"""
    try:
        if not mulaw_data or len(mulaw_data) < 10:
            return b""
            
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
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate(input=mulaw_data)
        
        if process.returncode != 0:
            logger.error(f"Erro ffmpeg mulaw->wav: {stderr.decode()}")
            return b""
            
        return stdout
        
    except Exception as e:
        logger.error(f"Erro convertendo mulaw para WAV: {e}")
        return b""


async def convert_wav_to_mulaw_async(wav_data: bytes) -> bytes:
    """Converte WAV para mulaw usando ffmpeg"""
    try:
        if not wav_data or len(wav_data) < 44:  # Mínimo para header WAV
            return b""
            
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-i", "pipe:0",
            "-ar", "8000",
            "-ac", "1",
            "-f", "mulaw",
            "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate(input=wav_data)
        
        if process.returncode != 0:
            logger.error(f"Erro ffmpeg wav->mulaw: {stderr.decode()}")
            return b""
            
        return stdout
        
    except Exception as e:
        logger.error(f"Erro convertendo WAV para mulaw: {e}")
        return b""


@router.get("/health")
async def health_check():
    """Endpoint para verificar se o servidor está funcionando"""
    return {"status": "healthy", "websocket_url": config.STREAM_WSS_URL}


@router.get("/test-websocket")
async def test_websocket():
    """Endpoint para testar se WebSocket está configurado corretamente"""
    try:
        import websockets
        import ssl
        
        # Extrair URL sem protocolo para teste
        url = config.STREAM_WSS_URL
        if url.startswith('wss://'):
            test_url = url.replace('wss://', 'ws://')  # Para teste local
        else:
            test_url = url
            
        return {
            "websocket_url": config.STREAM_WSS_URL,
            "test_url": test_url,
            "status": "configured"
        }
    except Exception as e:
        return {"error": str(e), "status": "error"}
import openai, io, asyncio, audioop
from app import config
from elevenlabs.client import ElevenLabs

openai.api_key = config.OPENAI_API_KEY
client = ElevenLabs(
    api_key=config.ELEVEN_API_KEY,
)

async def transcribe(mulaw_bytes: bytes) -> str:
    try:
        # Converte mulaw para linear PCM (que o Whisper entende)
        # Twilio envia em 8kHz mulaw
        pcm_data = audioop.ulaw2lin(mulaw_bytes, 2)
        
        # Cria um arquivo WAV temporário em memória
        wav_buffer = io.BytesIO()
        
        # Escreve header WAV manualmente (8kHz, mono, 16-bit)
        wav_buffer.write(b'RIFF')
        wav_buffer.write((len(pcm_data) + 36).to_bytes(4, 'little'))
        wav_buffer.write(b'WAVE')
        wav_buffer.write(b'fmt ')
        wav_buffer.write((16).to_bytes(4, 'little'))
        wav_buffer.write((1).to_bytes(2, 'little'))  # PCM
        wav_buffer.write((1).to_bytes(2, 'little'))  # Mono
        wav_buffer.write((8000).to_bytes(4, 'little'))  # 8kHz
        wav_buffer.write((16000).to_bytes(4, 'little'))  # Byte rate
        wav_buffer.write((2).to_bytes(2, 'little'))  # Block align
        wav_buffer.write((16).to_bytes(2, 'little'))  # Bits per sample
        wav_buffer.write(b'data')
        wav_buffer.write(len(pcm_data).to_bytes(4, 'little'))
        wav_buffer.write(pcm_data)
        
        wav_bytes = wav_buffer.getvalue()
        
        response = await openai.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.wav", wav_bytes, "audio/wav"),
            language="pt"
        )
        return response.text.strip()
        
    except Exception as e:
        print(f"Erro na transcrição: {e}")
        return ""

async def synthesize(text: str) -> bytes:
    try:
        audio_stream = client.generate(
            text=text,
            voice=config.VOICE_ID,
            model="eleven_multilingual_v2",
            stream=False,  # Mudou para False para simplificar
        )
        
        # Se não for stream, audio_stream já são os bytes
        if hasattr(audio_stream, 'read'):
            return audio_stream.read()
        else:
            return audio_stream
            
    except Exception as e:
        print(f"Erro na síntese: {e}")
        return b""
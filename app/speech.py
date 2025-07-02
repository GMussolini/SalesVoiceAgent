import openai, io, asyncio
from app import config

from elevenlabs.client import ElevenLabs

openai.api_key = config.OPENAI_API_KEY
client = ElevenLabs(
    api_key=config.ELEVEN_API_KEY,
)

async def transcribe(wav_bytes: bytes) -> str:
    return (
        await openai.audio.transcriptions.create(
            model="whisper-1",
            file=("chunk.wav", wav_bytes, "audio/wav"),
            language="pt"
        )
    ).text.strip()

async def synthesize(text: str) -> bytes:
    audio_stream = client.generate(
        text=text,
        voice=config.VOICE_ID,
        model="eleven_multilingual_v2",
        stream=True,
    )
    buf = io.BytesIO()
    async for chunk in audio_stream:
        buf.write(chunk)
    return buf.getvalue()
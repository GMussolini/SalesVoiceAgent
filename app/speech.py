import openai
import io
import asyncio
import audioop
from app import config
from elevenlabs.client import ElevenLabs

openai.api_key = config.OPENAI_API_KEY
client = ElevenLabs(
    api_key=config.ELEVEN_API_KEY,
)

async def transcribe(wav_bytes: bytes) -> str:
    """
    Transcreve áudio WAV usando OpenAI Whisper
    """
    try:
        if not wav_bytes or len(wav_bytes) < 100:  # Muito pequeno para ser áudio válido
            return ""
            
        # Cria um arquivo temporário em memória
        audio_file = io.BytesIO(wav_bytes)
        audio_file.name = "audio.wav"  # Whisper precisa do nome do arquivo
        
        response = await openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="pt",
            response_format="text"
        )
        
        return response.strip() if response else ""
        
    except Exception as e:
        print(f"Erro na transcrição: {e}")
        return ""


async def transcribe_mulaw(mulaw_bytes: bytes) -> str:
    """
    Transcreve áudio mulaw convertendo primeiro para WAV
    """
    try:
        if not mulaw_bytes or len(mulaw_bytes) < 10:
            return ""
            
        # Converte mulaw para linear PCM (16-bit)
        pcm_data = audioop.ulaw2lin(mulaw_bytes, 2)
        
        # Cria arquivo WAV em memória
        wav_buffer = io.BytesIO()
        
        # Header WAV para 8kHz, mono, 16-bit
        sample_rate = 8000
        num_channels = 1
        bits_per_sample = 16
        byte_rate = sample_rate * num_channels * bits_per_sample // 8
        block_align = num_channels * bits_per_sample // 8
        
        # Escreve header RIFF
        wav_buffer.write(b'RIFF')
        wav_buffer.write((36 + len(pcm_data)).to_bytes(4, 'little'))
        wav_buffer.write(b'WAVE')
        
        # Escreve chunk fmt
        wav_buffer.write(b'fmt ')
        wav_buffer.write((16).to_bytes(4, 'little'))  # Tamanho do chunk fmt
        wav_buffer.write((1).to_bytes(2, 'little'))   # Formato PCM
        wav_buffer.write(num_channels.to_bytes(2, 'little'))
        wav_buffer.write(sample_rate.to_bytes(4, 'little'))
        wav_buffer.write(byte_rate.to_bytes(4, 'little'))
        wav_buffer.write(block_align.to_bytes(2, 'little'))
        wav_buffer.write(bits_per_sample.to_bytes(2, 'little'))
        
        # Escreve chunk data
        wav_buffer.write(b'data')
        wav_buffer.write(len(pcm_data).to_bytes(4, 'little'))
        wav_buffer.write(pcm_data)
        
        wav_bytes = wav_buffer.getvalue()
        return await transcribe(wav_bytes)
        
    except Exception as e:
        print(f"Erro na transcrição mulaw: {e}")
        return ""


async def synthesize(text: str) -> bytes:
    """
    Sintetiza texto em áudio usando ElevenLabs
    """
    try:
        if not text.strip():
            return b""
            
        # Gera áudio usando ElevenLabs
        audio_generator = client.generate(
            text=text,
            voice=config.VOICE_ID,
            model="eleven_multilingual_v2",
            stream=True,  # Usa stream para melhor performance
        )
        
        # Coleta todos os chunks de áudio
        audio_chunks = []
        for chunk in audio_generator:
            if chunk:
                audio_chunks.append(chunk)
        
        # Junta todos os chunks
        return b"".join(audio_chunks)
        
    except Exception as e:
        print(f"Erro na síntese: {e}")
        return b""


async def synthesize_to_wav(text: str, sample_rate: int = 22050) -> bytes:
    """
    Sintetiza texto e retorna como WAV com sample rate específico
    """
    try:
        audio_bytes = await synthesize(text)
        if not audio_bytes:
            return b""
            
        # Se precisar converter para WAV com sample rate específico
        # usando ffmpeg
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-i", "pipe:0",
            "-ar", str(sample_rate),
            "-ac", "1",
            "-f", "wav",
            "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        
        stdout, _ = await process.communicate(input=audio_bytes)
        return stdout
        
    except Exception as e:
        print(f"Erro na síntese para WAV: {e}")
        return b""
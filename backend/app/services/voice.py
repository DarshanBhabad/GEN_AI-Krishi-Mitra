from io import BytesIO
from pathlib import Path
import shutil
import subprocess
import tempfile

from fastapi import UploadFile
from openai import OpenAI

from app.core.config import settings
from app.services.ai import AIUnavailableError


ALLOWED_AUDIO_TYPES = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/flac": ".flac",
}


class VoiceService:
    def __init__(self) -> None:
        self.client = (
            OpenAI(api_key=settings.api_key, base_url=settings.normalized_base_url)
            if settings.api_key and settings.normalized_base_url
            else None
        )

    async def transcribe(self, upload: UploadFile, data: bytes, language: str) -> str:
        client = self.client
        model_id = settings.transcription_model_id
        if not settings.has_asr or client is None or not model_id:
            raise AIUnavailableError("Speech recognition is not configured; set TRANSCRIPTION_MODEL_ID.")
        mime_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
        suffix = ALLOWED_AUDIO_TYPES.get(mime_type)
        audio_data = data
        filename = upload.filename or f"recording{suffix or '.bin'}"
        if not suffix:
            audio_data, filename, mime_type = self._convert_with_ffmpeg(data)
        result = client.audio.transcriptions.create(
            model=model_id,
            file=(filename, BytesIO(audio_data), mime_type),
            language=language,
        )
        text = getattr(result, "text", "")
        if not text.strip():
            raise ValueError("Speech recognition returned an empty transcript. Please record again.")
        return text.strip()

    @staticmethod
    def _convert_with_ffmpeg(data: bytes) -> tuple[bytes, str, str]:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise ValueError(
                "Unsupported audio type. Upload WAV, MP3, M4A, WebM, OGG, or FLAC; "
                "install FFmpeg to convert other formats."
            )
        try:
            with tempfile.TemporaryDirectory(prefix="agri-audio-") as directory:
                source = Path(directory) / "input-audio"
                output = Path(directory) / "normalized.wav"
                source.write_bytes(data)
                subprocess.run(
                    [
                        ffmpeg, "-nostdin", "-v", "error", "-y", "-i", str(source),
                        "-t", "120", "-ac", "1", "-ar", "16000", "-f", "wav", str(output),
                    ],
                    check=True,
                    timeout=30,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
                return output.read_bytes(), "recording.wav", "audio/wav"
        except (OSError, subprocess.SubprocessError) as error:
            raise ValueError("FFmpeg could not decode this audio file.") from error

    def synthesize(self, text: str) -> tuple[bytes, str]:
        if not settings.has_tts or self.client is None:
            raise AIUnavailableError("Speech synthesis is not configured; set TTS_MODEL_ID and TTS_VOICE.")
        response = self.client.audio.speech.create(
            model=settings.tts_model_id,
            voice=settings.tts_voice,
            input=text,
        )
        return response.read(), "audio/mpeg"


voice_service = VoiceService()

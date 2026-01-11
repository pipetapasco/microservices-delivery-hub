"""Audio handler for downloading and transcribing audio files with thread-safe model loading."""

import asyncio
import contextlib
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from faster_whisper import WhisperModel
import config
import httpx
from logger import get_logger

from core.exceptions import AudioProcessingError, AudioSizeLimitError, InvalidMimeTypeError

logger = get_logger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="whisper")

ALLOWED_AUDIO_TYPES = [
    "audio/ogg",
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/webm",
    "audio/amr",
]


class AudioHandler:
    """Handles audio download, validation, and transcription with thread-safe model loading."""

    def __init__(self):
        self._whisper_model = None
        self._model_loaded = False
        self._model_lock = threading.Lock()

    def _load_whisper_model(self):
        """
        Lazy load Whisper model with double-checked locking.
        Prevents multiple threads from loading the model simultaneously.
        """
        if self._model_loaded:
            return

        with self._model_lock:
            if self._model_loaded:
                return

            try:
                logger.info(f"Loading Whisper model: {config.WHISPER_MODEL_SIZE}")
                self._whisper_model = WhisperModel(
                    config.WHISPER_MODEL_SIZE, device="cpu", compute_type="int8"
                )
                self._model_loaded = True
                logger.info("Whisper model loaded successfully")
            except Exception:
                logger.error("Failed to load Whisper model", exc_info=True)
                self._whisper_model = None
                self._model_loaded = True

    async def validate_media(
        self, media_url: str, media_content_type: str, auth: tuple | None = None
    ) -> int:
        """
        Validate media before downloading.
        Returns content length if valid, raises exception otherwise.
        """
        if not media_content_type:
            raise InvalidMimeTypeError("No content type provided")

        if not any(media_content_type.startswith(t) for t in ALLOWED_AUDIO_TYPES):
            raise InvalidMimeTypeError(f"Unsupported audio type: {media_content_type}")

        max_size = config.MAX_AUDIO_SIZE_MB * 1024 * 1024

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.head(media_url, auth=auth)
                content_length = int(response.headers.get("content-length", 0))

                if content_length > max_size:
                    raise AudioSizeLimitError(
                        f"Audio size {content_length} exceeds limit of {max_size} bytes"
                    )

                return content_length

        except httpx.RequestError:
            logger.error("Failed to validate media", exc_info=True)
            raise AudioProcessingError("Cannot validate audio file")

    async def download_audio(
        self, media_url: str, media_content_type: str, auth: tuple | None = None
    ) -> str:
        """
        Download audio file with size validation.
        Returns path to downloaded file.
        """
        await self.validate_media(media_url, media_content_type, auth)

        extension = media_content_type.split("/")[-1].split(";")[0]
        if "opus" in extension or "ogg" in extension:
            extension = "ogg"

        filename = f"{uuid.uuid4()}.{extension}"
        filepath = os.path.join(config.AUDIO_STORAGE_PATH, filename)

        try:
            if not os.path.exists(config.AUDIO_STORAGE_PATH):
                os.makedirs(config.AUDIO_STORAGE_PATH)

            max_size = config.MAX_AUDIO_SIZE_MB * 1024 * 1024
            downloaded = 0

            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("GET", media_url, auth=auth) as response:
                    response.raise_for_status()

                    with open(filepath, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            downloaded += len(chunk)
                            if downloaded > max_size:
                                raise AudioSizeLimitError(
                                    "Audio size limit exceeded during download"
                                )
                            f.write(chunk)

            return filepath

        except httpx.RequestError:
            self._cleanup_file(filepath)
            logger.error("Failed to download audio", exc_info=True)
            raise AudioProcessingError("Cannot download audio file")
        except AudioSizeLimitError:
            self._cleanup_file(filepath)
            raise

    def _transcribe_sync(self, filepath: str) -> str | None:
        """Synchronous transcription (runs in thread pool)."""
        self._load_whisper_model()

        if not self._whisper_model:
            raise AudioProcessingError("Whisper model not available")

        try:
            segments, info = self._whisper_model.transcribe(filepath, beam_size=5)
            text = " ".join([segment.text for segment in segments]).strip()
            return text if text else None
        except Exception:
            logger.error("Transcription failed", exc_info=True)
            raise AudioProcessingError("Transcription failed")

    async def transcribe(self, filepath: str) -> str | None:
        """
        Transcribe audio file asynchronously.
        Runs CPU-intensive Whisper in thread pool to avoid blocking.
        """
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(_executor, self._transcribe_sync, filepath)
        finally:
            self._cleanup_file(filepath)

    def _cleanup_file(self, filepath: str) -> None:
        """Clean up temporary audio file."""
        if filepath and os.path.exists(filepath):
            with contextlib.suppress(Exception):
                os.remove(filepath)


_audio_handler: AudioHandler | None = None
_handler_lock = threading.Lock()


def get_audio_handler() -> AudioHandler:
    """Get audio handler singleton with thread-safe initialization."""
    global _audio_handler

    if _audio_handler is not None:
        return _audio_handler

    with _handler_lock:
        if _audio_handler is None:
            _audio_handler = AudioHandler()

    return _audio_handler

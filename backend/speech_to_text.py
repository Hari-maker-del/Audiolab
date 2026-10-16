"""Optional local speech-to-text using faster-whisper.

This module is deliberately lazy: Audiolab's existing TTS install does not need
the extra STT dependency until the user opts into transcription.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

_model = None
_model_lock = threading.Lock()
_model_name = os.getenv("AUDIOLAB_STT_MODEL", "small")
_model_device = os.getenv("AUDIOLAB_STT_DEVICE", "cpu")
_model_compute = os.getenv("AUDIOLAB_STT_COMPUTE_TYPE", "int8")

LANGUAGE_CODES = {
    "Tamil": "ta",
    "Telugu": "te",
    "Malayalam": "ml",
    "Hindi": "hi",
    "Kannada": "kn",
    "Bengali": "bn",
    "Gujarati": "gu",
    "Marathi": "mr",
    "Odia": "or",
    "Punjabi": "pa",
    "Assamese": "as",
    "English": "en",
}

WHISPER_LANGUAGE_NAMES = {
    "ta": "ta", "te": "te", "ml": "ml", "hi": "hi", "kn": "kn",
    "bn": "bn", "gu": "gu", "mr": "mr", "or": "or", "pa": "pa",
    "as": "as", "en": "en",
}


class SpeechToTextUnavailable(RuntimeError):
    """Raised when local STT dependencies are not installed."""


def status() -> dict:
    try:
        import importlib.util
        installed = importlib.util.find_spec("faster_whisper") is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        installed = False
    return {
        "id": "faster-whisper",
        "name": "faster-whisper (local)",
        "task": "speech-to-text",
        "state": "loaded" if _model is not None else ("not_configured" if not installed else "not_loaded"),
        "available": installed,
        "loaded": _model is not None,
        "model": _model_name,
        "device": _model_device,
        "compute_type": _model_compute,
        "note": "Runs locally. First use downloads model weights; CPU transcription can be slow.",
    }


def _get_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        try:
            from faster_whisper import WhisperModel
        except Exception as exc:
            raise SpeechToTextUnavailable(
                "Local speech-to-text is not installed. From the Audiolab repository root, run "
                r".\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-speech.txt"
            ) from exc
        try:
            _model = WhisperModel(
                _model_name,
                device=_model_device,
                compute_type=_model_compute,
            )
        except Exception as exc:
            raise SpeechToTextUnavailable(
                f"Could not load faster-whisper model '{_model_name}' on {_model_device}: {exc}"
            ) from exc
    return _model


def transcribe(path: str | Path, language: str | None = None) -> dict:
    requested = (language or "").strip()
    if requested and requested not in LANGUAGE_CODES:
        raise ValueError(f"Unsupported transcription language: {requested}")
    lang_code = LANGUAGE_CODES.get(requested) if requested else None
    model = _get_model()
    segments, info = model.transcribe(
        str(path),
        language=lang_code,
        vad_filter=True,
        beam_size=5,
    )
    rows = [
        {
            "start": round(float(item.start), 3),
            "end": round(float(item.end), 3),
            "text": item.text.strip(),
        }
        for item in segments
        if item.text and item.text.strip()
    ]
    text = " ".join(item["text"] for item in rows).strip()
    if not text:
        raise ValueError("No speech was detected. Try a clearer recording or a different language.")
    return {
        "text": text,
        "language": getattr(info, "language", None),
        "language_probability": round(float(getattr(info, "language_probability", 0.0)), 4),
        "duration": round(float(getattr(info, "duration", 0.0)), 3),
        "segments": rows,
        "model": _model_name,
        "device": _model_device,
        "provider": "local",
    }

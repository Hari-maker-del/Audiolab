"""Optional local text-to-music generation with MusicGen-small.

Weights are downloaded from Hugging Face on first generation. This module never
calls a hosted inference API. Loading/generation is serialized to limit RAM/VRAM use.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import threading

MODEL_ID = os.getenv("AUDIOLAB_MUSIC_MODEL", "facebook/musicgen-small")
_MIN_SECONDS = 5
_MAX_SECONDS = 15
_MAX_PROMPT_CHARS = 500
_model = None
_processor = None
_device = None
_lock = threading.Lock()


class MusicGenerationUnavailable(RuntimeError):
    """Raised when optional MusicGen dependencies are unavailable."""


class MusicGenerationFailed(RuntimeError):
    """Raised when model loading or generation fails."""


def music_generation_status() -> dict:
    installed = importlib.util.find_spec("torch") is not None and importlib.util.find_spec("transformers") is not None
    return {
        "id": "musicgen-small",
        "name": "MusicGen Small",
        "task": "text-to-music-generation",
        "model_id": MODEL_ID,
        "state": "loaded" if _model is not None else ("not_loaded" if installed else "dependencies_missing"),
        "available": installed,
        "loaded": _model is not None,
        "device": _device or "not_loaded",
        "note": (
            "First generation downloads model weights. Short clips are recommended; CPU generation can be slow."
            if installed else
            "Install backend/requirements-music.txt to enable local MusicGen."
        ),
        "duration_seconds": {"min": _MIN_SECONDS, "max": _MAX_SECONDS},
    }


def validate_music_request(prompt: str, duration: float) -> str:
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("Describe the music you want to generate.")
    if len(prompt) > _MAX_PROMPT_CHARS:
        raise ValueError(f"Music prompt must be {_MAX_PROMPT_CHARS} characters or fewer.")
    if not _MIN_SECONDS <= duration <= _MAX_SECONDS:
        raise ValueError(f"AI music duration must be between {_MIN_SECONDS} and {_MAX_SECONDS} seconds.")
    return prompt


def _load_model():
    global _model, _processor, _device
    if _model is not None:
        return
    if importlib.util.find_spec("torch") is None or importlib.util.find_spec("transformers") is None:
        raise MusicGenerationUnavailable(
            "MusicGen dependencies are missing. Run: "
            "python -m pip install -r backend/requirements-music.txt"
        )
    try:
        import torch
        from transformers import AutoProcessor, MusicgenForConditionalGeneration

        _device = "cuda" if torch.cuda.is_available() else "cpu"
        _processor = AutoProcessor.from_pretrained(MODEL_ID)
        _model = MusicgenForConditionalGeneration.from_pretrained(MODEL_ID)
        _model.to(_device)
        _model.eval()
    except Exception as exc:
        _model = None
        _processor = None
        _device = None
        raise MusicGenerationFailed(
            "Could not load MusicGen. Check internet access for the first model download, "
            "available disk/RAM/VRAM, and the optional dependencies. Details: "
            + str(exc)[-1200:]
        ) from exc


def generate_ai_music(prompt: str, duration: float, output: str | Path) -> str:
    """Generate a real music waveform from a text prompt and save it as a WAV."""
    prompt = validate_music_request(prompt, duration)
    if not _lock.acquire(blocking=False):
        raise MusicGenerationFailed("Another AI music task is running. Wait for it to finish and retry.")
    try:
        _load_model()
        import soundfile as sf
        import torch

        inputs = _processor(text=[prompt], padding=True, return_tensors="pt")
        inputs = {key: value.to(_device) if hasattr(value, "to") else value for key, value in inputs.items()}
        # MusicGen's decoder produces roughly 50 audio-codec frames per second.
        max_new_tokens = max(1, int(round(duration * float(_model.config.audio_encoder.frame_rate))))
        with torch.inference_mode():
            audio_values = _model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=True)
        audio = audio_values[0].detach().float().cpu().numpy()
        if audio.ndim == 2:
            audio = audio.T
        if audio.size == 0:
            raise MusicGenerationFailed("MusicGen returned an empty audio result.")
        sample_rate = int(_model.config.audio_encoder.sampling_rate)
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output), audio, sample_rate, subtype="PCM_16")
        return str(output)
    except (MusicGenerationUnavailable, MusicGenerationFailed, ValueError):
        raise
    except Exception as exc:
        raise MusicGenerationFailed("AI music generation failed: " + str(exc)[-1200:]) from exc
    finally:
        _lock.release()

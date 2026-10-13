"""Optional local OpenVoice V1 voice-to-voice conversion.

This is separate from the IndicF5 text-to-speech engine. It converts an existing
source performance toward the timbre of a reference recording. Timing and
emotional detail may change; this module does not promise exact preservation.
"""
from __future__ import annotations

import importlib.util
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODEL_ROOT = BASE_DIR / "models" / "openvoice_v1"
CONVERTER_DIR = MODEL_ROOT / "checkpoints" / "converter"
CONFIG_PATH = CONVERTER_DIR / "config.json"
CHECKPOINT_PATH = CONVERTER_DIR / "checkpoint.pth"

_engine = None
_engine_lock = threading.Lock()


class VoiceConversionUnavailable(RuntimeError):
    """Raised when the optional conversion model cannot be loaded."""


def _openvoice_installed() -> bool:
    try:
        return importlib.util.find_spec("openvoice") is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


_REQUIRED_MODULES = (
    "openvoice",
    "wavmark",
    "eng_to_ipa",
    "inflect",
    "unidecode",
    "pypinyin",
    "cn2an",
    "jieba",
)


def _missing_dependencies() -> list[str]:
    missing: list[str] = []
    for module_name in _REQUIRED_MODULES:
        try:
            present = importlib.util.find_spec(module_name) is not None
        except (ImportError, ValueError, ModuleNotFoundError):
            present = False
        if not present:
            missing.append(module_name)
    return missing


def _device_status() -> str:
    try:
        import torch
        return "cuda:0" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "unknown"


def get_voice_conversion_status() -> dict:
    files_present = CONFIG_PATH.is_file() and CHECKPOINT_PATH.is_file()
    package_installed = _openvoice_installed()
    missing_dependencies = _missing_dependencies()
    loaded = _engine is not None

    if loaded:
        state = "loaded"
    elif not files_present:
        state = "model_files_missing"
    elif missing_dependencies:
        state = "dependencies_missing"
    else:
        state = "ready_to_load"

    return {
        "id": "openvoice-v1",
        "name": "MyShell OpenVoice V1 ToneColorConverter",
        "task": "voice-to-voice conversion",
        "license": "MIT",
        "state": state,
        "available": bool(files_present and not missing_dependencies),
        "loaded": loaded,
        "model_files_present": files_present,
        "package_installed": package_installed,
        "missing_dependencies": missing_dependencies,
        "device": getattr(_engine, "device", _device_status()) if loaded else _device_status(),
        "model_directory": "backend/models/openvoice_v1/checkpoints/converter",
        "setup_command": r".\scripts\setup-voice-conversion.ps1",
        "note": "Local reference-conditioned conversion. Output timbre, timing, and emotion may differ from the input.",
    }


def _get_engine():
    global _engine
    if _engine is not None:
        return _engine

    with _engine_lock:
        if _engine is not None:
            return _engine

        if not CONFIG_PATH.is_file() or not CHECKPOINT_PATH.is_file():
            raise VoiceConversionUnavailable(
                "OpenVoice V1 model files are missing. Run "
                r".\scripts\setup-voice-conversion.ps1 from the Audiolab repository root."
            )

        try:
            import torch
            from openvoice.api import ToneColorConverter
        except Exception as exc:
            raise VoiceConversionUnavailable(
                "OpenVoice dependencies are not installed in Audiolab's Python environment. "
                r"Run .\scripts\setup-voice-conversion.ps1 from the repository root. "
                f"Import error: {exc}"
            ) from exc

        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        try:
            # OpenVoice's optional watermark support is enabled by default.
            converter = ToneColorConverter(str(CONFIG_PATH), device=device)
            converter.load_ckpt(str(CHECKPOINT_PATH))
        except Exception as exc:
            raise VoiceConversionUnavailable(
                f"OpenVoice could not load its checkpoint on {device}: {exc}"
            ) from exc

        _engine = type("LoadedOpenVoice", (), {})()
        _engine.converter = converter
        _engine.device = device
        _engine.inference_lock = threading.Lock()
        return _engine


def _profile_segment(audio, sample_rate: int, librosa):
    """Choose a speech-rich segment for speaker embedding only; never edit source output."""
    import numpy as np

    intervals = librosa.effects.split(audio, top_db=35)
    if len(intervals):
        start, end = max(intervals, key=lambda pair: int(pair[1]) - int(pair[0]))
        segment = audio[int(start):int(end)]
    else:
        segment = audio

    max_samples = sample_rate * 8
    if len(segment) > max_samples:
        middle = len(segment) // 2
        begin = max(0, middle - max_samples // 2)
        segment = segment[begin:begin + max_samples]

    if len(segment) < sample_rate:
        raise ValueError(
            "Each recording must contain at least one second of usable speech. "
            "Use a clearer, longer voice sample."
        )

    if not np.isfinite(segment).all():
        raise ValueError("The audio contains invalid numeric samples.")

    return segment


def convert_voice(source_path: str, target_path: str, output_path: str) -> str:
    """Convert source speech toward a reference voice and write a WAV result."""
    import librosa
    import numpy as np
    import soundfile as sf

    engine = _get_engine()
    converter = engine.converter
    sample_rate = int(converter.hps.data.sampling_rate)

    source, _ = librosa.load(source_path, sr=sample_rate, mono=True)
    target, _ = librosa.load(target_path, sr=sample_rate, mono=True)

    if source.size == 0 or target.size == 0:
        raise ValueError("The source or target reference contains no decodable audio.")
    if len(source) / sample_rate < 1:
        raise ValueError("The source recording must contain at least one second of speech.")
    if len(target) / sample_rate < 1:
        raise ValueError("The target reference must contain at least one second of speech.")
    if len(source) / sample_rate > 240:
        raise ValueError("The source recording is longer than the 4-minute local conversion limit.")
    if len(target) / sample_rate > 60:
        raise ValueError("The target reference is longer than the 60-second reference limit.")
    if not np.isfinite(source).all() or not np.isfinite(target).all():
        raise ValueError("The audio contains invalid numeric samples.")

    output = Path(output_path)
    source_wav = output.with_name(output.stem + "-source.wav")
    source_profile_wav = output.with_name(output.stem + "-source-profile.wav")
    target_profile_wav = output.with_name(output.stem + "-target-profile.wav")

    try:
        # The full source performance is resampled to the model's expected format.
        # A speech-rich crop is used only to estimate the source speaker embedding.
        sf.write(str(source_wav), source, sample_rate)
        sf.write(
            str(source_profile_wav),
            _profile_segment(source, sample_rate, librosa),
            sample_rate,
        )
        sf.write(
            str(target_profile_wav),
            _profile_segment(target, sample_rate, librosa),
            sample_rate,
        )

        with engine.inference_lock:
            source_embedding = converter.extract_se(str(source_profile_wav))
            target_embedding = converter.extract_se(str(target_profile_wav))
            converter.convert(
                audio_src_path=str(source_wav),
                src_se=source_embedding,
                tgt_se=target_embedding,
                output_path=str(output),
                message="@Audiolab",
            )

        if not output.is_file() or output.stat().st_size <= 44:
            raise RuntimeError("The conversion model did not produce a valid WAV file.")
        return str(output)
    finally:
        for temporary in (source_wav, source_profile_wav, target_profile_wav):
            temporary.unlink(missing_ok=True)

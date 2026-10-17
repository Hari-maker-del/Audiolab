"""Strict, dependency-free validation for Audiolab real-inference inputs and outputs."""
from __future__ import annotations

import json
import math
from pathlib import Path
import re
from io import BytesIO
import wave
import zipfile

SUPPORTED_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".flac", ".aac", ".webm", ".opus"}
REQUIRED_RENDER_FILES = {"dubbed_voice.wav", "subtitles.srt", "segments.json"}
SRT_CUE = re.compile(
    r"(?m)^\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+"
    r"\d{2}:\d{2}:\d{2},\d{3}\s*\n.+",
    re.DOTALL,
)


class AudioValidationError(ValueError):
    """Raised when an audio input or inference artifact is malformed."""


def validate_audio_input(path: str | Path, *, max_bytes: int = 100 * 1024 * 1024) -> dict:
    """Validate an existing supported audio file before uploading it to the local API.

    Compressed formats receive extension/size/non-empty checks only; WAV files are
    structurally inspected using Python's standard-library wave decoder.
    """
    audio = Path(path).expanduser().resolve()
    if not audio.is_file():
        raise AudioValidationError(f"Audio file not found: {audio}")
    if audio.suffix.lower() not in SUPPORTED_AUDIO_SUFFIXES:
        raise AudioValidationError(
            f"Unsupported audio extension '{audio.suffix or '(none)'}'. Supported: "
            + ", ".join(sorted(SUPPORTED_AUDIO_SUFFIXES))
        )
    size = audio.stat().st_size
    if size <= 0:
        raise AudioValidationError("Audio file is empty.")
    if max_bytes <= 0:
        raise AudioValidationError("Audio size limit must be greater than zero.")
    if size > max_bytes:
        raise AudioValidationError(
            f"Audio file is {size} bytes; the configured preflight limit is {max_bytes} bytes. "
            "Choose a shorter/compressed clip or adjust the backend upload limit."
        )

    report = {"path": str(audio), "size_bytes": size, "format": audio.suffix.lower()}
    if audio.suffix.lower() == ".wav":
        try:
            with wave.open(str(audio), "rb") as wav:
                channels = wav.getnchannels()
                sample_rate = wav.getframerate()
                frames = wav.getnframes()
                sample_width = wav.getsampwidth()
                if channels < 1 or sample_rate < 1 or frames < 1 or sample_width < 1:
                    raise AudioValidationError(
                        "WAV file has invalid audio parameters or contains no frames."
                    )
                report.update({
                    "channels": channels,
                    "sample_rate_hz": sample_rate,
                    "duration_seconds": round(frames / sample_rate, 3),
                    "sample_width_bytes": sample_width,
                })
        except (wave.Error, EOFError, OSError) as exc:
            raise AudioValidationError(
                f"WAV file could not be decoded ({exc}). Export it again as a valid PCM WAV."
            ) from exc
    return report


def validate_segments(segments: object, *, require_text: bool = True) -> dict:
    """Validate the shape, timing, and text of transcription/render segments."""
    if not isinstance(segments, list) or not segments:
        raise AudioValidationError("Inference returned no timestamped segments.")
    previous_start = -1.0
    last_end = 0.0
    text_characters = 0
    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            raise AudioValidationError(f"Segment {index} is not a JSON object.")
        start, end = segment.get("start"), segment.get("end")
        if (isinstance(start, bool) or isinstance(end, bool)
                or not isinstance(start, (int, float)) or not isinstance(end, (int, float))
                or not math.isfinite(start) or not math.isfinite(end)):
            raise AudioValidationError(f"Segment {index} has invalid or non-finite timestamps.")
        if start < 0 or end <= start:
            raise AudioValidationError(f"Segment {index} must have start >= 0 and end > start.")
        if start < previous_start:
            raise AudioValidationError("Segments are not ordered by start timestamp.")
        previous_start = float(start)
        last_end = max(last_end, float(end))
        text = segment.get("source_text") or segment.get("translated_text") or segment.get("text")
        if require_text and (not isinstance(text, str) or not text.strip()):
            raise AudioValidationError(f"Segment {index} has no usable text.")
        if isinstance(text, str):
            text_characters += len(text.strip())
    return {
        "segment_count": len(segments),
        "last_end_seconds": round(last_end, 3),
        "text_characters": text_characters,
    }


def validate_render_archive(raw: bytes) -> dict:
    """Validate real render artifacts, not just a non-empty ZIP signature."""
    if len(raw) < 22 or raw[:2] != b"PK":
        raise AudioValidationError("Render download is not a valid ZIP archive.")
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            if archive.testzip() is not None:
                raise AudioValidationError("Render ZIP contains a corrupt file.")
            names = set(archive.namelist())
            missing = REQUIRED_RENDER_FILES - names
            if missing:
                raise AudioValidationError(
                    "Render ZIP is missing required files: " + ", ".join(sorted(missing))
                )
            contents = {name: archive.read(name) for name in REQUIRED_RENDER_FILES}
    except zipfile.BadZipFile as exc:
        raise AudioValidationError("Render download could not be opened as a ZIP archive.") from exc

    for name, data in contents.items():
        if not data:
            raise AudioValidationError(f"Render ZIP contains an empty required file: {name}")

    try:
        with wave.open(BytesIO(contents["dubbed_voice.wav"]), "rb") as wav:
            channels, sample_rate, frames = wav.getnchannels(), wav.getframerate(), wav.getnframes()
            sample_width = wav.getsampwidth()
            if channels < 1 or sample_rate < 1 or frames < 1 or sample_width < 1:
                raise AudioValidationError("dubbed_voice.wav has invalid parameters or no audio frames.")
            # Read the declared frames to catch truncated payloads.
            audio_bytes = wav.readframes(frames)
            expected_bytes = frames * channels * sample_width
            if len(audio_bytes) < expected_bytes:
                raise AudioValidationError("dubbed_voice.wav is truncated: fewer audio bytes than declared frames.")
            audio_report = {
                "channels": channels,
                "sample_rate_hz": sample_rate,
                "duration_seconds": round(frames / sample_rate, 3),
                "sample_width_bytes": sample_width,
            }
    except (wave.Error, EOFError, OSError) as exc:
        raise AudioValidationError(
            f"dubbed_voice.wav is not a valid readable WAV file ({exc})."
        ) from exc

    subtitles = contents["subtitles.srt"].decode("utf-8-sig", errors="replace").strip()
    if not SRT_CUE.search(subtitles):
        raise AudioValidationError("subtitles.srt contains no recognizable timestamped subtitle cue.")

    try:
        metadata = json.loads(contents["segments.json"].decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise AudioValidationError("segments.json is not valid UTF-8 JSON.") from exc
    if not isinstance(metadata, dict):
        raise AudioValidationError("segments.json must contain a JSON object.")
    segment_report = validate_segments(metadata.get("segments"))
    return {
        "archive_entries": sorted(names),
        "audio": audio_report,
        "subtitles": {"cue_count": len(re.findall(r"(?m)^\d+\s*$", subtitles))},
        "segments": segment_report,
    }

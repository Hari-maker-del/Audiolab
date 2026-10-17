from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import wave
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from audiolab_inference_validation import (
    AudioValidationError,
    validate_audio_input,
    validate_render_archive,
    validate_segments,
)


def _wav_bytes(*, frames: int = 2400, sample_rate: int = 24000) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * frames)
    return output.getvalue()


def _archive(*, wav_payload: bytes | None = None, subtitles: str | None = None, metadata: str | None = None) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("dubbed_voice.wav", wav_payload if wav_payload is not None else _wav_bytes())
        archive.writestr("subtitles.srt", subtitles if subtitles is not None else
                         "1\n00:00:00,000 --> 00:00:00,100\nவணக்கம்\n")
        archive.writestr("segments.json", metadata if metadata is not None else json.dumps({
            "segments": [{"start": 0.0, "end": 0.1, "translated_text": "வணக்கம்"}]
        }))
    return output.getvalue()


def test_valid_wav_input_reports_duration_and_parameters(tmp_path):
    audio = tmp_path / "speech.wav"
    audio.write_bytes(_wav_bytes(frames=4800, sample_rate=24000))
    report = validate_audio_input(audio)
    assert report["sample_rate_hz"] == 24000
    assert report["duration_seconds"] == 0.2
    assert report["size_bytes"] > 44


def test_audio_input_rejects_missing_empty_unsupported_and_malformed_wav(tmp_path):
    with pytest.raises(AudioValidationError, match="not found"):
        validate_audio_input(tmp_path / "missing.wav")
    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    with pytest.raises(AudioValidationError, match="empty"):
        validate_audio_input(empty)
    unsupported = tmp_path / "clip.xyz"
    unsupported.write_bytes(b"audio")
    with pytest.raises(AudioValidationError, match="Unsupported"):
        validate_audio_input(unsupported)
    malformed = tmp_path / "bad.wav"
    malformed.write_bytes(b"not a wave")
    with pytest.raises(AudioValidationError, match="could not be decoded"):
        validate_audio_input(malformed)


def test_audio_input_enforces_size_limit(tmp_path):
    audio = tmp_path / "speech.mp3"
    audio.write_bytes(b"x" * 20)
    with pytest.raises(AudioValidationError, match="preflight limit"):
        validate_audio_input(audio, max_bytes=10)


def test_segments_require_valid_ordered_finite_timestamps_and_text():
    report = validate_segments([
        {"start": 0, "end": 0.5, "source_text": "hello"},
        {"start": 0.6, "end": 1.1, "source_text": "world"},
    ])
    assert report == {"segment_count": 2, "last_end_seconds": 1.1, "text_characters": 10}
    for segments in (
        [],
        [{"start": 0, "end": 0, "text": "bad"}],
        [{"start": float("nan"), "end": 1, "text": "bad"}],
        [{"start": 1, "end": 2, "text": "later"}, {"start": 0, "end": 1, "text": "earlier"}],
        [{"start": 0, "end": 1, "text": "  "}],
    ):
        with pytest.raises(AudioValidationError):
            validate_segments(segments)


def test_render_archive_validates_decodable_wav_subtitles_and_json():
    report = validate_render_archive(_archive())
    assert report["audio"]["duration_seconds"] == 0.1
    assert report["segments"]["segment_count"] == 1
    assert report["subtitles"]["cue_count"] == 1


@pytest.mark.parametrize("kwargs, message", [
    ({"wav_payload": b"fake-wave-payload"}, "not a valid readable WAV"),
    ({"subtitles": "no timestamps here"}, "no recognizable timestamped subtitle cue"),
    ({"metadata": "{not json"}, "not valid UTF-8 JSON"),
    ({"metadata": json.dumps({"segments": []})}, "no timestamped segments"),
])
def test_render_archive_rejects_invalid_artifacts(kwargs, message):
    with pytest.raises(AudioValidationError, match=message):
        validate_render_archive(_archive(**kwargs))

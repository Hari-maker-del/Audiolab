from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dubbing import build_srt, validate_dub_segments


def test_validate_segments_normalizes_and_preserves_timing():
    result = validate_dub_segments([
        {"start": 0, "end": 1.25, "text": "Hello", "translated_text": "வணக்கம்"},
        {"start": 1.5, "end": 2.75, "text": "World", "translated_text": "உலகம்"},
    ])
    assert result[0]["start"] == 0
    assert result[0]["end"] == 1.25
    assert result[0]["source_text"] == "Hello"
    assert result[1]["translated_text"] == "உலகம்"


def test_srt_timestamp_format_and_unicode():
    srt = build_srt([
        {"start": 1.2345, "end": 62.5, "translated_text": "வணக்கம்"},
    ])
    assert srt == "1\n00:00:01,235 --> 00:01:02,500\nவணக்கம்\n"


def test_validation_rejects_missing_translation():
    with pytest.raises(ValueError, match="reviewed translation"):
        validate_dub_segments([{"start": 0, "end": 1, "translated_text": ""}])


def test_validation_rejects_overlaps():
    with pytest.raises(ValueError, match="overlaps"):
        validate_dub_segments([
            {"start": 0, "end": 2, "translated_text": "First"},
            {"start": 1.5, "end": 3, "translated_text": "Second"},
        ])


def test_validation_rejects_invalid_timestamps():
    with pytest.raises(ValueError, match="end after"):
        validate_dub_segments([{"start": 2, "end": 1, "translated_text": "No"}])

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_music import music_generation_status, validate_music_request


def test_music_status_does_not_load_model():
    status = music_generation_status()

    assert status["id"] == "musicgen-small"
    assert status["task"] == "text-to-music-generation"
    assert status["state"] in {"loaded", "not_loaded", "dependencies_missing"}
    assert status["duration_seconds"] == {"min": 5, "max": 15}


@pytest.mark.parametrize("prompt,duration", [
    ("", 8),
    ("ambient instrumental", 4),
    ("ambient instrumental", 16),
    ("x" * 501, 8),
])
def test_music_request_validation_rejects_invalid_values(prompt, duration):
    with pytest.raises(ValueError):
        validate_music_request(prompt, duration)


def test_music_request_validation_trims_prompt():
    assert validate_music_request("  warm ambient music  ", 8) == "warm ambient music"

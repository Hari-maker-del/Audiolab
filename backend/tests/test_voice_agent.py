from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from voice_agent import create_reply, understand_intent


@pytest.mark.parametrize(
    "message,expected",
    [
        ("Please generate music for my video", "music_generation"),
        ("remove vocals from this song", "vocal_isolation"),
        ("convert this text to speech", "speech_generation"),
        ("please transcribe this recording", "transcription"),
        ("change voice in this clip", "voice_conversion"),
        ("help me use Audiolab", "help"),
        ("tell me a story", "general"),
    ],
)
def test_understands_common_audiolab_intents(message, expected):
    result = understand_intent(message)
    assert result["intent"] == expected
    assert result["original_text"] == message


def test_tamil_script_is_detected_as_language_hint():
    result = understand_intent("எனக்கு உதவி வேண்டும்")
    assert result["language_hint"] == "Tamil"


def test_empty_message_is_rejected():
    with pytest.raises(ValueError, match="Provide a spoken or typed request"):
        understand_intent("  ")


def test_reply_is_explicit_about_rule_based_mode():
    intent = understand_intent("help")
    reply = create_reply(intent)
    assert reply["intent"] == "help"
    assert "transcription" in reply["reply"]
    assert reply["mode"] == "local-rule-based-intent"

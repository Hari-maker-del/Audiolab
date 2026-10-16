"""Local-first conversational voice-agent orchestration.

This module intentionally uses explicit intent rules instead of pretending that a
hosted LLM is available. Speech recognition and spoken replies use optional local
models. Conversation history is supplied by the client and is not persisted server-side.
"""
from __future__ import annotations

import re


def understand_intent(text: str) -> dict:
    raw = (text or "").strip()
    value = raw.lower()
    if not value:
        raise ValueError("Provide a spoken or typed request.")

    intents = [
        ("music_generation", ("generate music", "create music", "make music", "music for", "இசை உருவாக்க", "பாட்டு உருவாக்க")),
        ("vocal_isolation", ("remove vocals", "isolate vocals", "separate vocals", "instrumental", "குரலை நீக்கு")),
        ("speech_generation", ("generate speech", "read this", "speak this", "text to speech", "குரலாக மாற்ற")),
        ("transcription", ("transcribe", "transcription", "what did i say", "write what i said", "என்ன சொன்னேன்")),
        ("voice_conversion", ("change voice", "convert voice", "voice changer")),
        ("help", ("help", "what can you do", "features", "how to use", "உதவி")),
    ]
    for intent, phrases in intents:
        if any(phrase in value for phrase in phrases):
            return {
                "intent": intent,
                "confidence": "rule_match",
                "language_hint": "Tamil" if re.search(r"[\u0B80-\u0BFF]", raw) else "unspecified",
                "original_text": raw[:2000],
            }

    return {
        "intent": "general",
        "confidence": "fallback",
        "language_hint": "Tamil" if re.search(r"[\u0B80-\u0BFF]", raw) else "unspecified",
        "original_text": raw[:2000],
    }


def create_reply(intent_result: dict) -> dict:
    intent = intent_result["intent"]
    replies = {
        "music_generation": (
            "I understood that you want to create music. Open Audio Studio, choose Text to music, "
            "describe the sound, and generate a short clip. MusicGen must be installed locally first."
        ),
        "vocal_isolation": (
            "I understood that you want to remove vocals. Open Audio Studio, choose Vocal isolation, "
            "and select your recording. Demucs must be installed locally first."
        ),
        "speech_generation": (
            "I understood that you want text converted to speech. Open Generate, enter your script, "
            "and provide an authorized reference recording with its exact transcript."
        ),
        "transcription": (
            "I can transcribe your recording with the optional local Whisper model. Install the speech "
            "requirements and upload the recording through the Transcribe tool."
        ),
        "voice_conversion": (
            "I understood that you want to convert a voice. Open Voice Conversion and configure the "
            "optional local OpenVoice model files first."
        ),
        "help": (
            "I can guide you through text-to-speech, transcription, voice conversion, vocal isolation, "
            "AI music generation and audio editing. Tell me which task you want to do."
        ),
        "general": (
            "I heard your request, but I could not confidently map it to an Audiolab action yet. "
            "Try asking for music generation, vocal isolation, speech generation, transcription, or help."
        ),
    }
    return {
        "intent": intent,
        "reply": replies.get(intent, replies["general"]),
        "speech_available": False,
        "mode": "local-rule-based-intent",
    }

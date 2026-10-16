"""Utilities for validating and exporting sentence-aligned dubbing projects.

The module contains pure helpers so timeline validation and SRT formatting can be
tested without downloading or loading speech models.
"""
from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


MAX_DUB_SEGMENTS = 120
MAX_DUB_DURATION_SECONDS = 30 * 60
MAX_SEGMENT_TEXT = 2000


def validate_dub_segments(rows: Any) -> list[dict]:
    """Validate editable source-time/translation rows and return normalized rows."""
    if not isinstance(rows, list) or not rows:
        raise ValueError("Provide at least one timed dubbing segment.")
    if len(rows) > MAX_DUB_SEGMENTS:
        raise ValueError(f"A dubbing project can contain at most {MAX_DUB_SEGMENTS} segments.")

    normalized = []
    previous_end = 0.0
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"Segment {index} must be an object.")
        try:
            start = float(row.get("start"))
            end = float(row.get("end"))
        except (TypeError, ValueError):
            raise ValueError(f"Segment {index} needs numeric start and end times.") from None
        if not math.isfinite(start) or not math.isfinite(end):
            raise ValueError(f"Segment {index} has an invalid timestamp.")
        if start < 0 or end <= start:
            raise ValueError(f"Segment {index} must end after its non-negative start time.")
        if end > MAX_DUB_DURATION_SECONDS:
            raise ValueError("Dubbing projects are limited to 30 minutes.")
        if start < previous_end - 0.01:
            raise ValueError(f"Segment {index} overlaps the previous segment. Adjust its timing.")
        source_text = str(row.get("source_text") or row.get("text") or "").strip()
        translated_text = str(row.get("translated_text") or "").strip()
        if len(source_text) > MAX_SEGMENT_TEXT or len(translated_text) > MAX_SEGMENT_TEXT:
            raise ValueError(f"Segment {index} text exceeds {MAX_SEGMENT_TEXT} characters.")
        if not translated_text:
            raise ValueError(f"Add a reviewed translation for segment {index}.")
        # The timeline and SRT use millisecond precision. Reject positive but
        # sub-millisecond slots that collapse to a zero-length normalized segment.
        normalized_start = round(start, 3)
        normalized_end = round(end, 3)
        if normalized_end <= normalized_start:
            raise ValueError(f"Segment {index} is too short to represent at millisecond precision.")
        normalized.append({
            "index": index,
            "start": normalized_start,
            "end": normalized_end,
            "source_text": source_text,
            "translated_text": translated_text,
        })
        previous_end = end
    return normalized


def _srt_milliseconds(seconds: float) -> int:
    return max(0, int((Decimal(str(seconds)) * Decimal(1000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


def _srt_timestamp(seconds: float) -> str:
    total_ms = _srt_milliseconds(seconds)
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    whole_seconds, milliseconds = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def build_srt(segments: list[dict]) -> str:
    """Build UTF-8 SubRip subtitles and prevent zero-length rounded cues."""
    blocks = []
    for number, segment in enumerate(segments, start=1):
        start_ms = _srt_milliseconds(segment["start"])
        end_ms = _srt_milliseconds(segment["end"])
        # Distinct sub-millisecond boundaries can round to the same SRT millisecond.
        # Keep the exported cue valid; the render endpoint separately validates the
        # normalized timeline before this helper is called.
        if end_ms <= start_ms:
            end_ms = start_ms + 1
        blocks.append(
            f"{number}\n{_srt_timestamp(Decimal(start_ms) / Decimal(1000))} --> "
            f"{_srt_timestamp(Decimal(end_ms) / Decimal(1000))}\n{segment['translated_text']}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")

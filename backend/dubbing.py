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
        normalized.append({
            "index": index,
            "start": round(start, 3),
            "end": round(end, 3),
            "source_text": source_text,
            "translated_text": translated_text,
        })
        previous_end = end
    return normalized


def _srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int((Decimal(str(seconds)) * Decimal(1000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    whole_seconds, milliseconds = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def build_srt(segments: list[dict]) -> str:
    """Build UTF-8 SubRip subtitles using the supplied segment timecodes."""
    blocks = []
    for number, segment in enumerate(segments, start=1):
        blocks.append(
            f"{number}\n{_srt_timestamp(segment['start'])} --> "
            f"{_srt_timestamp(segment['end'])}\n{segment['translated_text']}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")

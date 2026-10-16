"""Deterministic local audio creation tools for Audiolab.

These are DSP-generated effects and musical sketches, not generative-AI model outputs.
They work offline after the core Python dependencies are installed.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

SAMPLE_RATE = 24000
EFFECTS = ("whoosh", "impact", "riser", "rain", "ambient", "laser", "chime")
MUSIC_STYLES = ("ambient", "cinematic", "lofi", "pulse")


def _envelope(length: int, attack: float = 0.02, release: float = 0.2) -> np.ndarray:
    if length <= 0:
        return np.zeros(0, dtype=np.float32)
    env = np.ones(length, dtype=np.float32)
    a = min(length, max(1, int(attack * SAMPLE_RATE)))
    r = min(length, max(1, int(release * SAMPLE_RATE)))
    env[:a] = np.linspace(0, 1, a, endpoint=False, dtype=np.float32)
    env[-r:] *= np.linspace(1, 0, r, endpoint=True, dtype=np.float32)
    return env


def _write(audio: np.ndarray, output: str | Path) -> str:
    audio = np.nan_to_num(np.asarray(audio, dtype=np.float32))
    if audio.size == 0:
        raise ValueError("Generated audio is empty.")
    peak = float(np.max(np.abs(audio)))
    if peak > 0:
        audio = audio / peak * 0.92
    sf.write(str(output), audio, SAMPLE_RATE, subtype="PCM_16")
    return str(output)


def generate_sound_effect(effect: str, duration: float, output: str | Path, seed: int = 7) -> str:
    if effect not in EFFECTS:
        raise ValueError(f"Unsupported effect. Choose from: {', '.join(EFFECTS)}.")
    if not 0.25 <= duration <= 20:
        raise ValueError("Sound-effect duration must be between 0.25 and 20 seconds.")
    n = int(SAMPLE_RATE * duration)
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    rng = np.random.default_rng(seed)
    env = _envelope(n, attack=min(0.08, duration * 0.2), release=min(0.7, duration * 0.45))

    if effect == "whoosh":
        noise = rng.normal(0, 1, n).astype(np.float32)
        sos = signal.butter(3, [250, 7000], btype="bandpass", fs=SAMPLE_RATE, output="sos")
        sweep = signal.sosfilt(sos, noise)
        # Clamp tiny negative floating-point values at sin(pi) before fractional power.
        swell = np.maximum(np.sin(np.linspace(0, np.pi, n, dtype=np.float32)), 0.0) ** 1.5
        audio = sweep * swell
    elif effect == "impact":
        sweep = np.sin(2 * np.pi * (95 - 30 * t / duration) * t)
        click = rng.normal(0, 1, n).astype(np.float32) * np.exp(-t * 35)
        audio = (sweep * np.exp(-t * 8) + 0.35 * click) * env
    elif effect == "riser":
        phase = 2 * np.pi * (100 * t + (1800 - 100) * t * t / (2 * duration))
        noise = rng.normal(0, 0.08, n).astype(np.float32)
        audio = (np.sin(phase) + noise) * np.linspace(0.03, 1, n, dtype=np.float32) * env
    elif effect == "rain":
        noise = rng.normal(0, 1, n).astype(np.float32)
        sos = signal.butter(3, 5000, btype="lowpass", fs=SAMPLE_RATE, output="sos")
        audio = signal.sosfilt(sos, noise) * 0.7
        drops = int(duration * 16)
        for _ in range(drops):
            idx = int(rng.integers(0, max(1, n - 120)))
            size = min(120, n - idx)
            audio[idx:idx + size] += rng.uniform(0.15, 0.65) * np.exp(-np.arange(size) / 18)
        audio *= 0.8
    elif effect == "ambient":
        noise = rng.normal(0, 1, n).astype(np.float32)
        sos = signal.butter(4, [80, 900], btype="bandpass", fs=SAMPLE_RATE, output="sos")
        drone = signal.sosfilt(sos, noise)
        audio = drone * 0.25 + 0.25 * np.sin(2 * np.pi * 55 * t)
    elif effect == "laser":
        freq = 1500 * np.exp(-t * 5) + 90
        phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
        audio = np.sin(phase) * np.exp(-t * 7)
    else:  # chime
        audio = np.zeros(n, dtype=np.float32)
        for at, freq, amp in ((0.0, 880, 1.0), (0.16, 1320, 0.65), (0.34, 1760, 0.4)):
            start = int(at * SAMPLE_RATE)
            if start >= n:
                continue
            length = n - start
            local_t = np.arange(length, dtype=np.float32) / SAMPLE_RATE
            audio[start:] += amp * np.sin(2 * np.pi * freq * local_t) * np.exp(-local_t * 5)
        audio *= env
    return _write(audio, output)


def generate_music_sketch(style: str, duration: float, output: str | Path, seed: int = 11) -> str:
    """Create a simple royalty-free procedural music bed, not AI-composed music."""
    if style not in MUSIC_STYLES:
        raise ValueError(f"Unsupported style. Choose from: {', '.join(MUSIC_STYLES)}.")
    if not 2 <= duration <= 60:
        raise ValueError("Music sketch duration must be between 2 and 60 seconds.")
    n = int(SAMPLE_RATE * duration)
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    rng = np.random.default_rng(seed)
    if style == "ambient":
        notes = (110.0, 164.81, 220.0, 329.63)
        audio = sum(np.sin(2 * np.pi * f * t + i * 0.2) / (i + 1) for i, f in enumerate(notes))
        slow = 0.55 + 0.25 * np.sin(2 * np.pi * 0.12 * t)
        audio = audio * slow
    elif style == "cinematic":
        notes = (55.0, 82.41, 110.0, 164.81, 220.0)
        audio = sum(np.sin(2 * np.pi * f * t) / (i + 1) for i, f in enumerate(notes))
        swell = np.minimum(1, t / 2) * np.minimum(1, np.maximum(0, duration - t) / 2)
        audio *= swell
    elif style == "lofi":
        beat = 0.5
        audio = np.zeros(n, dtype=np.float32)
        for start in np.arange(0, duration, beat):
            idx = int(start * SAMPLE_RATE)
            length = min(int(0.12 * SAMPLE_RATE), n - idx)
            if length > 0:
                local_t = np.arange(length, dtype=np.float32) / SAMPLE_RATE
                audio[idx:idx + length] += np.sin(2 * np.pi * 65 * local_t) * np.exp(-local_t * 25)
        chord = sum(np.sin(2 * np.pi * f * t) for f in (261.63, 311.13, 392.0))
        audio += 0.22 * chord * (0.6 + 0.4 * np.sin(2 * np.pi * 2 * t))
        audio += 0.025 * rng.normal(0, 1, n)
    else:
        gate = (np.sin(2 * np.pi * 2 * t) > 0).astype(np.float32)
        audio = gate * (np.sin(2 * np.pi * 55 * t) + 0.4 * np.sin(2 * np.pi * 110 * t))
        audio += 0.15 * np.sin(2 * np.pi * 440 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.25 * t))
    fade = _envelope(n, attack=min(0.5, duration / 4), release=min(1.5, duration / 3))
    return _write(np.asarray(audio, dtype=np.float32) * fade, output)

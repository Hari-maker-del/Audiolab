from pathlib import Path
import numpy as np
import librosa
import soundfile as sf


def analyze(path):
    y, sr = librosa.load(path, sr=16000, mono=True)
    if y.size == 0:
        raise ValueError("Empty reference audio.")
    duration = len(y) / sr
    rms = float(np.sqrt(np.mean(y * y)))
    frames = librosa.feature.rms(y=y)[0]
    silence = float(np.mean(frames < max(np.max(frames) * 0.05, 1e-5)))
    score = 100
    if duration < 5:
        score -= 30
    elif duration < 10:
        score -= 10
    if silence > 0.45:
        score -= 20
    if rms < 0.01:
        score -= 20
    return {
        "duration": round(duration, 2),
        "rms": round(rms, 4),
        "silence": round(silence, 3),
        "score": max(0, round(score)),
    }


def clean(src, dst):
    y, sr = librosa.load(src, sr=24000, mono=True)
    y, _ = librosa.effects.trim(y, top_db=32)
    peak = np.max(np.abs(y))
    if peak:
        y = y / peak * 0.95
    sf.write(dst, y, sr)
    return dst

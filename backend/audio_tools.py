import librosa
import numpy as np
import soundfile as sf
from scipy import signal


def load_audio(path, sr=None):
    y, sample_rate = librosa.load(path, sr=sr, mono=True)
    if y.size == 0:
        raise ValueError("Audio file is empty.")
    return y.astype(np.float32), sample_rate


def write_audio(y, sr, output):
    y = np.nan_to_num(np.asarray(y, dtype=np.float32))
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    if peak > 1.0:
        y = y / peak * 0.99
    sf.write(output, y, sr, subtype="PCM_16")
    return output


def trim_audio(src, start, end, output):
    y, sr = load_audio(src)
    start_i = max(0, int(start * sr))
    end_i = min(len(y), int(end * sr))
    if end_i <= start_i:
        raise ValueError("End time must be greater than start time.")
    return write_audio(y[start_i:end_i], sr, output)


def normalize_audio(src, output, target_db=-1.0):
    y, sr = load_audio(src)
    peak = float(np.max(np.abs(y)))
    if peak > 0:
        y *= (10 ** (target_db / 20.0)) / peak
    return write_audio(y, sr, output)


def fade_audio(src, output, fade_in=0.0, fade_out=0.0):
    y, sr = load_audio(src)
    if fade_in > 0:
        n = min(len(y), max(1, int(fade_in * sr)))
        y[:n] *= np.linspace(0, 1, n, dtype=np.float32)
    if fade_out > 0:
        n = min(len(y), max(1, int(fade_out * sr)))
        y[-n:] *= np.linspace(1, 0, n, dtype=np.float32)
    return write_audio(y, sr, output)


def reverse_audio(src, output):
    y, sr = load_audio(src)
    return write_audio(y[::-1], sr, output)


def speed_audio(src, output, rate):
    if not 0.25 <= rate <= 4.0:
        raise ValueError("Speed must be between 0.25x and 4x.")
    y, sr = load_audio(src)
    return write_audio(librosa.effects.time_stretch(y, rate=rate), sr, output)


def pitch_audio(src, output, semitones):
    if not -12 <= semitones <= 12:
        raise ValueError("Pitch shift must be between -12 and +12 semitones.")
    y, sr = load_audio(src)
    return write_audio(librosa.effects.pitch_shift(y, sr=sr, n_steps=semitones), sr, output)


def remove_silence(src, output, top_db=32.0):
    y, sr = load_audio(src)
    result, _ = librosa.effects.trim(y, top_db=top_db)
    return write_audio(result, sr, output)


def enhance_voice(src, output):
    y, sr = load_audio(src)
    high = min(9000, sr // 2 - 100)
    if high <= 70:
        return write_audio(y, sr, output)
    sos = signal.butter(4, [70, high], btype="bandpass", fs=sr, output="sos")
    filtered = signal.sosfiltfilt(sos, y).astype(np.float32)
    return write_audio(np.tanh(filtered * 1.25), sr, output)


def merge_audio(paths, output):
    if not paths:
        raise ValueError("At least one audio file is required.")
    clips = []
    rates = []
    for path in paths:
        y, sr = load_audio(path)
        clips.append(y)
        rates.append(sr)
    target = rates[0]
    converted = [c if sr == target else librosa.resample(c, orig_sr=sr, target_sr=target) for c, sr in zip(clips, rates)]
    return write_audio(np.concatenate(converted), target, output)


def audio_quality(path):
    y, sr = load_audio(path)
    rms_frames = librosa.feature.rms(y=y)[0]
    duration = len(y) / sr
    peak = float(np.max(np.abs(y)))
    rms = float(np.sqrt(np.mean(y * y)))
    clipping = float(np.mean(np.abs(y) >= 0.999))
    silence = float(np.mean(rms_frames < max(float(np.max(rms_frames)) * 0.05, 1e-5)))
    score = 100
    if duration < 1: score -= 20
    if clipping > 0.01: score -= 25
    if rms < 0.01: score -= 20
    if silence > 0.5: score -= 15
    return {
        "duration": round(duration, 2),
        "sample_rate": sr,
        "peak": round(peak, 4),
        "rms": round(rms, 4),
        "clipping_ratio": round(clipping, 4),
        "silence_ratio": round(silence, 4),
        "quality_score": max(0, score),
        "notes": [
            "High clipping detected." if clipping > 0.01 else "No significant clipping detected.",
            "Very quiet recording." if rms < 0.01 else "Recording level is usable.",
        ],
    }

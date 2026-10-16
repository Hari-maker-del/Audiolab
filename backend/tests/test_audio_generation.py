from pathlib import Path
import sys

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audio_generation import EFFECTS, MUSIC_STYLES, generate_music_sketch, generate_sound_effect


@pytest.mark.parametrize("effect", EFFECTS)
def test_sound_effect_writes_valid_wav(tmp_path, effect):
    output = tmp_path / f"{effect}.wav"
    result = generate_sound_effect(effect, 0.5, output, seed=17)

    assert Path(result) == output
    audio, sample_rate = sf.read(output)
    assert sample_rate == 24000
    assert audio.size > 1000
    assert np.isfinite(audio).all()
    assert np.max(np.abs(audio)) <= 1.0


@pytest.mark.parametrize("style", MUSIC_STYLES)
def test_music_sketch_writes_valid_wav(tmp_path, style):
    output = tmp_path / f"{style}.wav"
    result = generate_music_sketch(style, 2, output, seed=19)

    assert Path(result) == output
    audio, sample_rate = sf.read(output)
    assert sample_rate == 24000
    assert audio.size == 48000
    assert np.isfinite(audio).all()
    assert np.max(np.abs(audio)) <= 1.0


def test_sound_effect_is_reproducible_with_same_seed(tmp_path):
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    generate_sound_effect("rain", 1, first, seed=23)
    generate_sound_effect("rain", 1, second, seed=23)

    assert np.array_equal(sf.read(first)[0], sf.read(second)[0])


@pytest.mark.parametrize("effect", ["", "unknown"])
def test_unknown_effect_is_rejected(tmp_path, effect):
    with pytest.raises(ValueError, match="Unsupported effect"):
        generate_sound_effect(effect, 1, tmp_path / "bad.wav")


@pytest.mark.parametrize("duration", [0.1, 20.1])
def test_invalid_sound_effect_duration_is_rejected(tmp_path, duration):
    with pytest.raises(ValueError, match="duration"):
        generate_sound_effect("whoosh", duration, tmp_path / "bad.wav")


def test_unknown_music_style_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Unsupported style"):
        generate_music_sketch("orchestral", 2, tmp_path / "bad.wav")


@pytest.mark.parametrize("duration", [1.9, 60.1])
def test_invalid_music_duration_is_rejected(tmp_path, duration):
    with pytest.raises(ValueError, match="duration"):
        generate_music_sketch("ambient", duration, tmp_path / "bad.wav")

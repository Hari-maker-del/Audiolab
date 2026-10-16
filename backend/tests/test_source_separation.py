from pathlib import Path

import pytest

from source_separation import (
    SeparationFailed,
    find_stems,
    separation_status,
)


def test_status_reports_optional_model_without_loading_it():
    status = separation_status()

    assert status["id"] == "demucs-htdemucs"
    assert status["task"] == "vocal-instrumental-separation"
    assert status["state"] in {"ready_to_download_weights", "dependencies_missing"}
    assert isinstance(status["package_installed"], bool)


def test_find_stems_returns_vocals_and_instrumental(tmp_path):
    track = tmp_path / "htdemucs" / "sample"
    track.mkdir(parents=True)
    vocals = track / "vocals.wav"
    instrumental = track / "no_vocals.wav"
    vocals.write_bytes(b"vocal")
    instrumental.write_bytes(b"instrumental")

    found_vocals, found_instrumental = find_stems(tmp_path)

    assert found_vocals == vocals
    assert found_instrumental == instrumental


def test_find_stems_fails_if_demucs_did_not_create_both_stems(tmp_path):
    track = tmp_path / "htdemucs" / "sample"
    track.mkdir(parents=True)
    (track / "vocals.wav").write_bytes(b"vocal")

    with pytest.raises(SeparationFailed, match="both vocals.wav and no_vocals.wav"):
        find_stems(tmp_path)

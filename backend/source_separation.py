"""Optional local vocal/instrumental separation powered by Demucs.

Demucs is installed separately from the core Audiolab requirements. The model weights
are downloaded by Demucs on first use. No cloud inference endpoint is used.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys


MODEL_NAME = os.getenv("AUDIOLAB_SEPARATION_MODEL", "htdemucs")
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("AUDIOLAB_SEPARATION_TIMEOUT_SECONDS", "1200"))


class SeparationUnavailable(RuntimeError):
    """Raised when optional separation dependencies are not installed."""


class SeparationFailed(RuntimeError):
    """Raised when the separator fails or does not produce both stems."""


def separation_status() -> dict:
    installed = importlib.util.find_spec("demucs") is not None
    return {
        "id": "demucs-htdemucs",
        "name": "Demucs (HTDemucs)",
        "task": "vocal-instrumental-separation",
        "state": "ready_to_download_weights" if installed else "dependencies_missing",
        "package_installed": installed,
        "model": MODEL_NAME,
        "device": "auto (CUDA when available, otherwise CPU)",
        "note": (
            "Model weights may download on first use. CPU processing can be slow."
            if installed else
            "Install the optional backend/requirements-separation.txt file to enable local source separation."
        ),
    }


def choose_device() -> str:
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def find_stems(output_root: Path) -> tuple[Path, Path]:
    """Find actual Demucs vocal and accompaniment outputs without assuming track names."""
    vocals = sorted(output_root.glob("**/vocals.wav"))
    instrumentals = sorted(output_root.glob("**/no_vocals.wav"))
    if not vocals or not instrumentals:
        raise SeparationFailed("Demucs finished without producing both vocals.wav and no_vocals.wav.")
    return vocals[0], instrumentals[0]


def separate_to_stems(input_path: Path, output_root: Path, timeout_seconds: int | None = None) -> tuple[Path, Path]:
    if not input_path.is_file() or input_path.stat().st_size == 0:
        raise ValueError("Choose a non-empty audio file.")
    if importlib.util.find_spec("demucs") is None:
        raise SeparationUnavailable(
            "Vocal isolation is not installed yet. Run: "
            "python -m pip install -r backend/requirements-separation.txt"
        )

    output_root.mkdir(parents=True, exist_ok=True)
    timeout = timeout_seconds if timeout_seconds is not None else DEFAULT_TIMEOUT_SECONDS
    if timeout < 1:
        raise ValueError("Separation timeout must be at least one second.")

    command = [
        sys.executable, "-m", "demucs.separate",
        "--name", MODEL_NAME,
        "--two-stems", "vocals",
        "--out", str(output_root),
        "--device", choose_device(),
        str(input_path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SeparationFailed(
            f"Separation exceeded the {timeout}-second limit. Try a shorter clip or increase "
            "AUDIOLAB_SEPARATION_TIMEOUT_SECONDS."
        ) from exc
    except OSError as exc:
        raise SeparationFailed("Could not start the local Demucs process.") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "No diagnostic output was returned.").strip()
        detail = detail[-1800:]
        raise SeparationFailed(f"Demucs failed (exit {result.returncode}): {detail}")

    return find_stems(output_root)

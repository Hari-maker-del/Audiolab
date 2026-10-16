#!/usr/bin/env python3
"""Audiolab local preflight: check Windows/Python dependencies and loopback API readiness.

No packages are installed, models are not downloaded, and no audio is submitted.
The API URL is deliberately restricted to loopback so this tool cannot probe a
publicly exposed inference server by accident.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request


REQUIRED_DISTRIBUTIONS = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "python-multipart": "python-multipart",
}
OPTIONAL_DISTRIBUTIONS = {
    "torch": "torch",
    "torchaudio": "torchaudio",
    "transformers": "transformers",
    "faster-whisper": "faster-whisper",
    "soundfile": "soundfile",
    "librosa": "librosa",
    "demucs": "demucs",
    "audiocraft": "audiocraft",
}
MIN_FREE_DISK_GB = 5


def validate_loopback_url(value: str) -> str:
    parsed = urllib.parse.urlparse((value or "").strip())
    if parsed.scheme != "http" or not parsed.hostname:
        raise ValueError("Use an http:// loopback URL such as http://127.0.0.1:8000.")
    host = parsed.hostname.lower()
    import ipaddress
    try:
        is_loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        is_loopback = host == "localhost"
    if not is_loopback:
        raise ValueError("Safety stop: diagnostics may only contact localhost/loopback APIs.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("API URL must not include credentials, query parameters, or a fragment.")
    return value.strip().rstrip("/")


def _distribution_status(names: dict[str, str]) -> dict[str, dict]:
    results = {}
    for import_name, distribution_name in names.items():
        try:
            version = importlib.metadata.version(distribution_name)
            results[import_name] = {"installed": True, "version": version}
        except importlib.metadata.PackageNotFoundError:
            results[import_name] = {"installed": False, "version": None}
    return results


def _health_check(base_url: str, timeout: float) -> dict:
    request = urllib.request.Request(base_url + "/health", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return {"reachable": False, "error": f"Health endpoint returned HTTP {response.status}."}
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"reachable": False, "error": f"Health endpoint returned HTTP {exc.code}."}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"reachable": False, "error": f"Could not reach local API: {exc}"}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"reachable": False, "error": "Health endpoint did not return valid JSON."}
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return {"reachable": False, "error": "Health response did not report status=ok."}
    inference = payload.get("inference") if isinstance(payload.get("inference"), dict) else {}
    feature_names = ("speech_to_text", "voice_conversion", "source_separation", "ai_music", "voice_agent")
    features = {}
    for name in feature_names:
        feature = payload.get(name)
        if isinstance(feature, dict):
            features[name] = {
                "state": feature.get("state", "unknown"),
                "available": feature.get("available"),
                "note": feature.get("note"),
            }
    return {
        "reachable": True,
        "product": payload.get("product"),
        "version": payload.get("version"),
        "device": payload.get("device", "unknown"),
        "inference": {
            "state": inference.get("state", "unknown"),
            "loaded": inference.get("loaded"),
            "model_id": inference.get("model_id"),
            "note": inference.get("note"),
        },
        "job_queue": payload.get("job_queue"),
        "features": features,
    }


def run_preflight(*, api_url: str = "http://127.0.0.1:8000", project_root: str | Path = ".",
                  minimum_free_gb: float = MIN_FREE_DISK_GB, timeout: float = 3.0) -> dict:
    base_url = validate_loopback_url(api_url)
    root = Path(project_root).expanduser().resolve()
    checks: list[dict] = []

    python_ok = sys.version_info >= (3, 11)
    checks.append({
        "name": "python_version", "status": "pass" if python_ok else "fail",
        "detail": f"{platform.python_implementation()} {platform.python_version()}",
        "recommendation": None if python_ok else "Install Python 3.11 or newer and rerun the local launcher.",
    })

    is_windows = platform.system() == "Windows"
    checks.append({
        "name": "operating_system", "status": "pass" if is_windows else "info",
        "detail": platform.platform(),
        "recommendation": None if is_windows else "Audiolab supports local development on other platforms too; the launcher instructions target Windows.",
    })

    required = _distribution_status(REQUIRED_DISTRIBUTIONS)
    missing_required = [name for name, item in required.items() if not item["installed"]]
    checks.append({
        "name": "backend_packages", "status": "fail" if missing_required else "pass",
        "detail": required,
        "recommendation": "Activate backend\\.venv and install backend\\requirements.txt." if missing_required else None,
    })

    optional = _distribution_status(OPTIONAL_DISTRIBUTIONS)
    missing_optional = [name for name, item in optional.items() if not item["installed"]]
    checks.append({
        "name": "optional_audio_packages", "status": "warn" if missing_optional else "pass",
        "detail": optional,
        "recommendation": "Some optional features may be unavailable. Use the project launcher/environment setup and install only the feature dependencies you need." if missing_optional else None,
    })

    disk_path = root if root.exists() else Path.cwd()
    try:
        free_gb = shutil.disk_usage(disk_path).free / (1024 ** 3)
        disk_status = "pass" if free_gb >= minimum_free_gb else "warn"
        disk_detail = f"{free_gb:.1f} GB free at {disk_path}"
        disk_recommendation = None if disk_status == "pass" else "Free disk space before downloading model weights or generating long audio."
    except OSError as exc:
        free_gb = None
        disk_status, disk_detail = "warn", f"Could not inspect disk space: {exc}"
        disk_recommendation = "Check available disk space manually."
    checks.append({"name": "disk_space", "status": disk_status, "detail": disk_detail, "free_gb": free_gb, "recommendation": disk_recommendation})

    venv = root / "backend" / ".venv"
    venv_python = venv / ("Scripts/python.exe" if is_windows else "bin/python")
    checks.append({
        "name": "project_virtual_environment", "status": "pass" if venv_python.is_file() else "warn",
        "detail": str(venv_python) if venv_python.is_file() else "Project backend virtual environment not found.",
        "recommendation": None if venv_python.is_file() else "Run START-AUDIOLAB.bat on Windows, or create backend/.venv and install backend/requirements.txt.",
    })

    health = _health_check(base_url, timeout)
    checks.append({
        "name": "local_api_health", "status": "pass" if health["reachable"] else "fail",
        "detail": health,
        "recommendation": None if health["reachable"] else "Start Audiolab with START-AUDIOLAB.bat and retry. Keep the API bound to 127.0.0.1.",
    })

    if health["reachable"] and health.get("inference", {}).get("loaded") is False:
        checks.append({
            "name": "model_loaded", "status": "info",
            "detail": "IndicF5 loads on first generation; not_loaded at startup is expected.",
            "recommendation": "Run a real, short generation smoke test to verify model downloads, memory, and device compatibility.",
        })

    statuses = [item["status"] for item in checks]
    overall = "fail" if "fail" in statuses else ("warn" if "warn" in statuses else "pass")
    return {
        "product": "Audiolab Local Preflight",
        "overall": overall,
        "api_url": base_url,
        "python": platform.python_version(),
        "project_root": str(root),
        "checks": checks,
        "summary": {
            "passed": statuses.count("pass"),
            "warnings": statuses.count("warn"),
            "failed": statuses.count("fail"),
            "informational": statuses.count("info"),
        },
        "notes": [
            "Preflight does not install dependencies, download model weights, or submit audio.",
            "A healthy API does not prove real model inference works.",
            "Optional feature packages may be absent when their features are not needed.",
            "Never expose the unauthenticated local inference API publicly.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--minimum-free-gb", type=float, default=MIN_FREE_DISK_GB)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only.")
    args = parser.parse_args(argv)
    try:
        report = run_preflight(api_url=args.api_url, project_root=args.project_root,
                               minimum_free_gb=args.minimum_free_gb, timeout=args.timeout)
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"=== {report['product']} ===")
        for check in report["checks"]:
            print(f"[{check['status'].upper()}] {check['name']}: {check['detail']}")
            if check.get("recommendation"):
                print("  Next step: " + check["recommendation"])
        print(f"Summary: {report['summary']}")
        print("\nModel inference is not verified by preflight; run the Phase 13 smoke test with real audio.")
    return 1 if report["overall"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())

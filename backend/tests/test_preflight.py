from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import audiolab_preflight as preflight


def _fake_health(*_args, **_kwargs):
    return {
        "reachable": True,
        "product": "Audiolab AI Audio Studio",
        "version": "2.9.0",
        "device": "cpu",
        "inference": {
            "state": "not_loaded", "loaded": False,
            "model_id": "ai4bharat/IndicF5",
            "note": "Loads on first generation",
        },
        "job_queue": {"pending": 0},
        "features": {"speech_to_text": {"state": "available", "available": True}},
    }


def _fake_distributions(names):
    return {name: {"installed": True, "version": "1.2.3"} for name in names}


def test_loopback_url_validation_rejects_remote_hosts_and_credentials():
    assert preflight.validate_loopback_url("http://127.0.0.1:8000/") == "http://127.0.0.1:8000"
    assert preflight.validate_loopback_url("http://localhost:8000") == "http://localhost:8000"
    with pytest.raises(ValueError, match="loopback"):
        preflight.validate_loopback_url("http://example.com:8000")
    with pytest.raises(ValueError, match="loopback"):
        preflight.validate_loopback_url("https://127.0.0.1:8000")
    with pytest.raises(ValueError, match="credentials"):
        preflight.validate_loopback_url("http://user:secret@127.0.0.1:8000")


def test_preflight_reports_ready_api_without_claiming_model_is_loaded(tmp_path, monkeypatch):
    monkeypatch.setattr(preflight, "_health_check", _fake_health)
    monkeypatch.setattr(preflight, "_distribution_status", _fake_distributions)
    monkeypatch.setattr(preflight.platform, "system", lambda: "Windows")
    venv_python = tmp_path / "backend" / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_bytes(b"fixture")
    report = preflight.run_preflight(project_root=tmp_path)
    assert report["overall"] == "pass"
    assert report["summary"]["failed"] == 0
    model = next(check for check in report["checks"] if check["name"] == "model_loaded")
    assert model["status"] == "info"
    assert model["detail"]["loaded"] is False if isinstance(model["detail"], dict) else "not_loaded" in model["detail"]
    assert any("does not prove real model inference" in note for note in report["notes"])


def test_preflight_fails_when_required_packages_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(preflight, "_health_check", _fake_health)
    monkeypatch.setattr(preflight, "_distribution_status", lambda names: {
        name: {"installed": name != "fastapi", "version": None if name == "fastapi" else "1.0"}
        for name in names
    })
    report = preflight.run_preflight(project_root=tmp_path)
    assert report["overall"] == "fail"
    packages = next(check for check in report["checks"] if check["name"] == "backend_packages")
    assert packages["status"] == "fail"
    assert "fastapi" in packages["detail"]


def test_preflight_reports_unreachable_api_and_optional_package_warnings(tmp_path, monkeypatch):
    monkeypatch.setattr(preflight, "_health_check", lambda *_a, **_k: {
        "reachable": False, "error": "connection refused"
    })
    monkeypatch.setattr(preflight, "_distribution_status", lambda names: {
        name: {"installed": name not in {"torch", "faster-whisper"}, "version": None}
        for name in names
    })
    report = preflight.run_preflight(project_root=tmp_path)
    assert report["overall"] == "fail"
    assert next(c for c in report["checks"] if c["name"] == "local_api_health")["status"] == "fail"
    assert next(c for c in report["checks"] if c["name"] == "optional_audio_packages")["status"] == "warn"


def test_preflight_machine_report_is_json_serializable(tmp_path, monkeypatch):
    monkeypatch.setattr(preflight, "_health_check", _fake_health)
    monkeypatch.setattr(preflight, "_distribution_status", _fake_distributions)
    report = preflight.run_preflight(project_root=tmp_path)
    parsed = json.loads(json.dumps(report))
    assert parsed["product"] == "Audiolab Local Preflight"
    assert {"passed", "warnings", "failed", "informational"} <= set(parsed["summary"])


def test_preflight_rejects_remote_api_before_any_network_call(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(preflight, "_health_check", lambda *_a, **_k: called.append(True))
    with pytest.raises(ValueError, match="loopback"):
        preflight.run_preflight(api_url="http://203.0.113.10:8000", project_root=tmp_path)
    assert called == []

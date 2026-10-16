from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from audiolab_e2e_smoke import SmokeTestError, run_smoke, validate_base_url, validate_render_zip


def _test_archive() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("dubbed_voice.wav", b"fake-wave-payload")
        archive.writestr("subtitles.srt", "1\n00:00:00,000 --> 00:00:01,000\nHello\n")
        archive.writestr("segments.json", '{"segments":[]}')
    return output.getvalue()


class FakeAudiolabServer:
    def __init__(self):
        self.job_id = "e2e-test-job"
        self.archive = _test_archive()
        self.submitted = False
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def _send(self, status, payload, content_type="application/json"):
                body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/health":
                    return self._send(200, {"status": "ok", "public_health_probe": True})
                if self.path.startswith("/jobs?"):
                    jobs = [{"job_id": outer.job_id, "kind": "dub-render", "status": "succeeded"}] if outer.submitted else []
                    return self._send(200, {"jobs": jobs, "count": len(jobs), "limit": 100})
                if self.path == "/jobs/" + outer.job_id:
                    if not outer.submitted:
                        return self._send(404, {"detail": "not found"})
                    return self._send(200, {
                        "job_id": outer.job_id, "kind": "dub-render", "status": "succeeded",
                        "result": {"download_url": "/jobs/" + outer.job_id + "/download"},
                        "error": None,
                    })
                if self.path == "/jobs/" + outer.job_id + "/download":
                    return self._send(200, outer.archive, "application/zip")
                return self._send(404, {"detail": "not found"})

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                if self.path != "/jobs/dub-render":
                    return self._send(404, {"detail": "not found"})
                outer.submitted = True
                return self._send(202, {"job_id": outer.job_id, "status": "queued"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self):
        return "http://127.0.0.1:" + str(self.server.server_port)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def test_base_url_only_accepts_loopback_http():
    assert validate_base_url("http://127.0.0.1:8000/") == "http://127.0.0.1:8000"
    assert validate_base_url("http://localhost:8000") == "http://localhost:8000"
    with pytest.raises(SmokeTestError, match="loopback"):
        validate_base_url("http://example.com:8000")
    with pytest.raises(SmokeTestError, match="loopback"):
        validate_base_url("https://127.0.0.1:8000")


def test_zip_validator_requires_real_zip_and_expected_outputs():
    with pytest.raises(SmokeTestError, match="ZIP signature"):
        validate_render_zip(b"<html>error</html>")
    incomplete = io.BytesIO()
    with zipfile.ZipFile(incomplete, "w") as archive:
        archive.writestr("dubbed_voice.wav", b"wav")
    with pytest.raises(SmokeTestError, match="missing required files"):
        validate_render_zip(incomplete.getvalue())
    assert set(validate_render_zip(_test_archive())) == {
        "dubbed_voice.wav", "subtitles.srt", "segments.json"
    }


def test_render_smoke_exercises_http_submit_poll_history_and_download(tmp_path):
    with FakeAudiolabServer() as server, tempfile.TemporaryDirectory() as source_dir:
        source_root = Path(source_dir)
        target_audio = source_root / "target.wav"
        target_audio.write_bytes(b"test target voice")
        manifest = source_root / "manifest.json"
        manifest.write_text(json.dumps({
            "target_audio": "target.wav",
            "target_language": "Tamil",
            "ref_text": "வணக்கம்",
            "segments": [{"start": 0, "end": 1, "translated_text": "வணக்கம்"}],
        }), encoding="utf-8")
        output = run_smoke(
            base_url=server.base_url,
            render_manifest=str(manifest),
            output_dir=str(tmp_path),
            timeout=1,
            on_message=lambda _message: None,
        )
        assert server.submitted is True
        assert output["health"] == "passed"
        assert output["history"] == "passed"
        assert output["jobs"][0]["status"] == "succeeded"
        assert Path(output["render_archive"]).is_file()
        assert set(output["archive_entries"]) == {
            "dubbed_voice.wav", "subtitles.srt", "segments.json"
        }


def test_smoke_stops_if_backend_health_is_invalid():
    class BadHealthHandler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass
        def do_GET(self):
            body = b'{"status":"down"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), BadHealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(SmokeTestError, match="healthy API"):
            run_smoke(base_url="http://127.0.0.1:" + str(server.server_port),
                      on_message=lambda _message: None)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

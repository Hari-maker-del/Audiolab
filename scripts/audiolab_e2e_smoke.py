#!/usr/bin/env python3
"""Run a safe end-to-end smoke test against a locally running Audiolab API.

This script never contacts a non-loopback host. Health/history checks are read-only.
Actual transcription/render inference runs only when the corresponding inputs are supplied.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from io import BytesIO
from typing import Callable


REQUIRED_RENDER_FILES = {"dubbed_voice.wav", "subtitles.srt", "segments.json"}
LOOPBACK_NAMES = {"localhost", "127.0.0.1", "::1"}


class SmokeTestError(RuntimeError):
    """Raised when a backend smoke-test assertion fails."""


def validate_base_url(value: str) -> str:
    parsed = urllib.parse.urlparse((value or "").strip())
    if parsed.scheme != "http" or not parsed.hostname:
        raise SmokeTestError("API URL must be an http:// loopback address (for example http://127.0.0.1:8000).")
    hostname = parsed.hostname.lower()
    try:
        is_loopback = hostname in LOOPBACK_NAMES or socket.getaddrinfo(hostname, parsed.port or 80)[0][4][0] and __import__("ipaddress").ip_address(socket.getaddrinfo(hostname, parsed.port or 80)[0][4][0]).is_loopback
    except (OSError, ValueError, IndexError):
        is_loopback = False
    if not is_loopback:
        raise SmokeTestError("Safety stop: the smoke test only permits a loopback backend. Do not expose your local inference API publicly.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SmokeTestError("API URL must not contain credentials, a query string, or a fragment.")
    return value.strip().rstrip("/")


def _request(base_url: str, path: str, *, method: str = "GET", body: bytes | None = None,
             content_type: str | None = None, api_key: str | None = None, timeout: float = 10):
    headers = {"Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = content_type
    if api_key:
        headers["X-Audiolab-API-Key"] = api_key
    request = urllib.request.Request(base_url + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            detail = json.loads(raw.decode("utf-8")).get("detail", raw.decode("utf-8")[:300])
        except (ValueError, AttributeError):
            detail = raw.decode("utf-8", errors="replace")[:300]
        raise SmokeTestError(f"{method} {path} returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SmokeTestError(f"Could not reach local Audiolab API at {base_url}: {exc}") from exc


def _json_request(base_url: str, path: str, **kwargs):
    status, _, raw = _request(base_url, path, **kwargs)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise SmokeTestError(f"{path} returned invalid JSON.") from exc
    if not isinstance(value, dict):
        raise SmokeTestError(f"{path} returned a JSON value with the wrong shape.")
    return status, value


def _multipart(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
    boundary = "----AudiolabSmoke" + uuid.uuid4().hex
    pieces: list[bytes] = []
    for key, value in fields.items():
        pieces.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
            value.encode("utf-8"),
            b"\r\n",
        ])
    filename = file_path.name.replace('"', "")
    mime = "audio/wav" if file_path.suffix.lower() == ".wav" else "application/octet-stream"
    pieces.extend([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode(),
        f"Content-Type: {mime}\r\n\r\n".encode(),
        file_path.read_bytes(),
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    return b"".join(pieces), f"multipart/form-data; boundary={boundary}"


def validate_render_zip(raw: bytes) -> list[str]:
    if len(raw) < 22 or raw[:2] != b"PK":
        raise SmokeTestError("Render download is not a valid ZIP archive (missing ZIP signature).")
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            if archive.testzip() is not None:
                raise SmokeTestError("Render ZIP contains a corrupt file.")
            names = set(archive.namelist())
            missing = REQUIRED_RENDER_FILES - names
            if missing:
                raise SmokeTestError("Render ZIP is missing required files: " + ", ".join(sorted(missing)))
            for name in REQUIRED_RENDER_FILES:
                if archive.getinfo(name).file_size == 0:
                    raise SmokeTestError(f"Render ZIP contains an empty required file: {name}")
            return sorted(names)
    except zipfile.BadZipFile as exc:
        raise SmokeTestError("Render download could not be opened as a ZIP archive.") from exc


def _poll_job(base_url: str, job_id: str, *, timeout: float, api_key: str | None,
              on_message: Callable[[str], None], poll_interval: float = 1.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _, job = _json_request(base_url, "/jobs/" + urllib.parse.quote(job_id, safe=""), api_key=api_key, timeout=10)
        if job.get("job_id") != job_id or job.get("status") not in {"queued", "running", "succeeded", "failed"}:
            raise SmokeTestError("Backend returned an invalid job status record.")
        on_message(f"Job {job_id}: {job['status']}")
        if job["status"] == "succeeded":
            return job
        if job["status"] == "failed":
            raise SmokeTestError(f"Audio job failed: {job.get('error') or 'No error details were recorded.'}")
        time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))
    raise SmokeTestError(f"Timed out waiting for job {job_id} after {timeout:g} seconds.")


def _assert_history_contains(base_url: str, job_id: str, api_key: str | None) -> None:
    _, history = _json_request(base_url, "/jobs?limit=100", api_key=api_key)
    jobs = history.get("jobs")
    if not isinstance(jobs, list) or not any(isinstance(job, dict) and job.get("job_id") == job_id for job in jobs):
        raise SmokeTestError(f"Completed job {job_id} was not found in GET /jobs history.")


def run_smoke(*, base_url: str = "http://127.0.0.1:8000", timeout: float = 1800,
              transcribe_audio: str | None = None, render_manifest: str | None = None,
              output_dir: str = "audiolab-e2e-results", api_key: str | None = None,
              on_message: Callable[[str], None] = print) -> dict:
    base_url = validate_base_url(base_url)
    if timeout <= 0:
        raise SmokeTestError("Timeout must be greater than zero.")

    _, health = _json_request(base_url, "/health", api_key=api_key)
    if health.get("status") not in {"ok", "healthy"} and health.get("public_health_probe") is not True:
        raise SmokeTestError("Backend health response did not confirm a healthy API.")
    on_message("PASS: backend health endpoint responded.")
    _, history = _json_request(base_url, "/jobs?limit=5", api_key=api_key)
    if not isinstance(history.get("jobs"), list) or not isinstance(history.get("count"), int):
        raise SmokeTestError("GET /jobs returned an invalid history response.")
    on_message(f"PASS: job history endpoint responded ({history['count']} jobs in returned page).")

    summary: dict = {"base_url": base_url, "health": "passed", "history": "passed", "jobs": [], "render_archive": None}
    if transcribe_audio:
        audio = Path(transcribe_audio).expanduser().resolve()
        if not audio.is_file():
            raise SmokeTestError(f"Transcription audio file not found: {audio}")
        body, content_type = _multipart({"source_language": ""}, "source_file", audio)
        _, submitted = _json_request(base_url, "/jobs/dub-transcribe", method="POST", body=body,
                                     content_type=content_type, api_key=api_key, timeout=30)
        job_id = submitted.get("job_id")
        if submitted.get("status") != "queued" or not isinstance(job_id, str) or not job_id:
            raise SmokeTestError("Transcription endpoint did not return a queued job ID.")
        job = _poll_job(base_url, job_id, timeout=timeout, api_key=api_key, on_message=on_message)
        result = job.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("segments"), list) or not result["segments"]:
            raise SmokeTestError("Transcription succeeded but returned no timestamped segments.")
        _assert_history_contains(base_url, job_id, api_key)
        on_message(f"PASS: transcription job persisted with {len(result['segments'])} segment(s).")
        summary["jobs"].append({"job_id": job_id, "kind": "dub-transcribe", "status": job["status"], "segments": len(result["segments"])})

    if render_manifest:
        manifest_path = Path(render_manifest).expanduser().resolve()
        if not manifest_path.is_file():
            raise SmokeTestError(f"Render manifest not found: {manifest_path}")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SmokeTestError(f"Could not read render manifest JSON: {exc}") from exc
        if not isinstance(manifest, dict):
            raise SmokeTestError("Render manifest must be a JSON object.")
        target = (manifest_path.parent / str(manifest.get("target_audio", ""))).resolve()
        segments = manifest.get("segments")
        target_language = manifest.get("target_language")
        ref_text = manifest.get("ref_text")
        if not target.is_file() or not isinstance(segments, list) or not segments or not isinstance(target_language, str) or not isinstance(ref_text, str) or not ref_text.strip():
            raise SmokeTestError("Manifest requires target_audio, target_language, ref_text, and a non-empty segments array.")
        body, content_type = _multipart({
            "segments_json": json.dumps(segments, ensure_ascii=False),
            "target_language": target_language,
            "ref_text": ref_text,
            "consent": "true",
        }, "target_file", target)
        _, submitted = _json_request(base_url, "/jobs/dub-render", method="POST", body=body,
                                     content_type=content_type, api_key=api_key, timeout=30)
        job_id = submitted.get("job_id")
        if submitted.get("status") != "queued" or not isinstance(job_id, str) or not job_id:
            raise SmokeTestError("Render endpoint did not return a queued job ID.")
        job = _poll_job(base_url, job_id, timeout=timeout, api_key=api_key, on_message=on_message)
        _assert_history_contains(base_url, job_id, api_key)
        on_message("PASS: render job persisted in job history.")
        _, _, archive = _request(base_url, "/jobs/" + urllib.parse.quote(job_id, safe="") + "/download",
                                 api_key=api_key, timeout=60)
        entries = validate_render_zip(archive)
        out_dir = Path(output_dir).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        destination = out_dir / f"audiolab-render-{job_id}.zip"
        destination.write_bytes(archive)
        on_message(f"PASS: downloaded and validated ZIP ({', '.join(entries)}).")
        on_message(f"Saved archive: {destination}")
        summary["jobs"].append({"job_id": job_id, "kind": "dub-render", "status": job["status"]})
        summary["render_archive"] = str(destination)
        summary["archive_entries"] = entries

    if not transcribe_audio and not render_manifest:
        on_message("NOTE: only read-only health/history checks ran. Supply --transcribe-audio and/or --render-manifest to exercise actual local model inference.")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=1800, help="Maximum wait for each actual model job, in seconds.")
    parser.add_argument("--transcribe-audio", help="Audio file to submit to the local speech-to-text job endpoint.")
    parser.add_argument("--render-manifest", help="JSON manifest describing a real dubbing render (see docs/PHASE13_E2E.md).")
    parser.add_argument("--output-dir", default="audiolab-e2e-results")
    parser.add_argument("--api-key", default=os.getenv("AUDIOLAB_API_KEY") or None, help="Optional local backend API key; defaults to AUDIOLAB_API_KEY.")
    args = parser.parse_args(argv)
    try:
        summary = run_smoke(base_url=args.base_url, timeout=args.timeout,
                            transcribe_audio=args.transcribe_audio, render_manifest=args.render_manifest,
                            output_dir=args.output_dir, api_key=args.api_key)
    except SmokeTestError as exc:
        print(f"FAIL: {exc}")
        return 1
    print("Smoke test summary:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

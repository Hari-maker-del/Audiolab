from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_queue import public_job_view


def test_public_render_job_view_never_exposes_local_artifact_path():
    job = {
        "job_id": "render-123",
        "kind": "dub-render",
        "status": "succeeded",
        "created_at": "2026-10-16T10:00:00+00:00",
        "started_at": "2026-10-16T10:00:01+00:00",
        "finished_at": "2026-10-16T10:00:02+00:00",
        "result": {
            "artifact_path": "C:/private/audiolab/outputs/result.zip",
            "filename": "audiolab-dubbing-project.zip",
        },
        "error": None,
    }

    public = public_job_view(job)

    assert public["result"] == {
        "download_url": "/jobs/render-123/download",
        "filename": "audiolab-dubbing-project.zip",
    }
    assert "artifact_path" not in str(public)
    assert "C:/private" not in str(public)


def test_public_transcription_job_view_keeps_useful_result():
    job = {
        "job_id": "transcribe-123",
        "kind": "dub-transcribe",
        "status": "succeeded",
        "created_at": "2026-10-16T10:00:00+00:00",
        "started_at": None,
        "finished_at": None,
        "result": {"language": "Tamil", "segments": [{"start": 0, "end": 1}]},
        "error": None,
    }

    public = public_job_view(job)

    assert public["result"]["language"] == "Tamil"
    assert len(public["result"]["segments"]) == 1
    assert public["job_id"] == "transcribe-123"


def test_public_failed_job_view_preserves_safe_error_message():
    job = {
        "job_id": "failed-123",
        "kind": "dub-render",
        "status": "failed",
        "created_at": "2026-10-16T10:00:00+00:00",
        "started_at": None,
        "finished_at": "2026-10-16T10:01:00+00:00",
        "result": None,
        "error": "Local model unavailable",
    }

    public = public_job_view(job)

    assert public["status"] == "failed"
    assert public["error"] == "Local model unavailable"
    assert public["result"] is None

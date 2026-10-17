from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_queue import public_job_view


def test_voice_generation_job_view_hides_local_artifact_path():
    job = {
        "job_id": "voice-job-123",
        "kind": "voice-generate",
        "status": "succeeded",
        "created_at": "2026-10-17T00:00:00+00:00",
        "started_at": "2026-10-17T00:00:01+00:00",
        "finished_at": "2026-10-17T00:00:03+00:00",
        "result": {
            "artifact_path": r"C:\\private\\Audiolab\\outputs\\audiolab-generated-job.wav",
            "filename": "audiolab-tamil-voice.wav",
            "media_type": "audio/wav",
            "sample_rate": 24000,
            "duration_seconds": 2.5,
        },
        "error": None,
    }

    public = public_job_view(job)

    assert public["status"] == "succeeded"
    assert public["result"]["download_url"] == "/jobs/voice-job-123/download"
    assert public["result"]["filename"] == "audiolab-tamil-voice.wav"
    assert public["result"]["media_type"] == "audio/wav"
    assert public["result"]["sample_rate"] == 24000
    assert public["result"]["duration_seconds"] == 2.5
    assert "artifact_path" not in public["result"]
    assert "private" not in repr(public)


def test_queued_voice_generation_does_not_claim_a_download_is_ready():
    job = {
        "job_id": "voice-job-queued",
        "kind": "voice-generate",
        "status": "queued",
        "created_at": "2026-10-17T00:00:00+00:00",
        "result": None,
        "error": None,
    }

    public = public_job_view(job)

    assert public["status"] == "queued"
    assert public["result"] is None

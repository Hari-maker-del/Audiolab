from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_queue import BoundedJobQueue
from job_store import PersistentJobStore


def test_completed_job_history_survives_store_reopen(tmp_path):
    db_path = tmp_path / "audiolab-jobs.sqlite3"
    store = PersistentJobStore(db_path)
    jobs = BoundedJobQueue(max_workers=1, max_pending=2, store=store)

    job_id = jobs.submit("test", lambda value: {"answer": value}, 42)
    deadline = time.monotonic() + 2
    job = jobs.get(job_id)
    while job and job["status"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.01)
        job = jobs.get(job_id)

    assert job is not None
    assert job["status"] == "succeeded"
    assert job["result"] == {"answer": 42}

    reopened = PersistentJobStore(db_path)
    restored = reopened.get(job_id)
    assert restored is not None
    assert restored["status"] == "succeeded"
    assert restored["result"] == {"answer": 42}


def test_interrupted_job_is_marked_failed_on_restart(tmp_path):
    db_path = tmp_path / "audiolab-jobs.sqlite3"
    store = PersistentJobStore(db_path)
    store.save({
        "job_id": "interrupted-job",
        "kind": "dub-transcribe",
        "status": "running",
        "created_at": "2026-10-16T10:00:00+00:00",
        "started_at": "2026-10-16T10:00:01+00:00",
        "finished_at": None,
        "result": None,
        "error": None,
    })

    recovered = PersistentJobStore(db_path).get("interrupted-job")
    assert recovered is not None
    assert recovered["status"] == "failed"
    assert "Backend restarted" in recovered["error"]
    assert recovered["finished_at"]


def test_job_history_can_filter_by_status_and_limit(tmp_path):
    store = PersistentJobStore(tmp_path / "audiolab-jobs.sqlite3")
    for index, status in enumerate(("succeeded", "failed", "succeeded")):
        store.save({
            "job_id": f"job-{index}",
            "kind": "test",
            "status": status,
            "created_at": f"2026-10-16T10:00:0{index}+00:00",
            "started_at": None,
            "finished_at": f"2026-10-16T10:01:0{index}+00:00",
            "result": {"index": index},
            "error": None,
        })

    assert len(store.list(limit=2)) == 2
    failed = store.list(limit=10, status="failed")
    assert len(failed) == 1
    assert failed[0]["job_id"] == "job-1"


def test_history_pruning_keeps_the_most_recent_records(tmp_path):
    store = PersistentJobStore(tmp_path / "audiolab-jobs.sqlite3", max_history=20)
    for index in range(25):
        store.save({
            "job_id": f"job-{index}",
            "kind": "test",
            "status": "succeeded",
            "created_at": f"2026-10-16T10:{index:02d}:00+00:00",
            "started_at": None,
            "finished_at": f"2026-10-16T10:{index:02d}:01+00:00",
            "result": None,
            "error": None,
        })

    records = store.list(limit=100)
    assert len(records) == 20
    assert "job-24" in {job["job_id"] for job in records}
    assert "job-0" not in {job["job_id"] for job in records}

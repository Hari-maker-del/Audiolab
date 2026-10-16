"""Bounded in-process worker queue with optional persistent job metadata.

The worker queue itself remains single-process: callable arguments and in-flight work
are not resumable. When a SQLite store is supplied, history survives restarts and
unfinished records are recovered as explicit failures.
"""
from datetime import datetime, timezone
import logging
import queue
import threading
import uuid


class QueueFullError(RuntimeError):
    """Raised when the bounded pending queue cannot accept another task."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def public_job_view(job: dict) -> dict:
    """Return a stable API-safe job representation without local artifact paths."""
    result = job.get("result")
    if job.get("status") == "succeeded" and job.get("kind") == "dub-render":
        result = {
            "download_url": f"/jobs/{job['job_id']}/download",
            "filename": "audiolab-dubbing-project.zip",
        }
    return {
        "job_id": job["job_id"],
        "kind": job["kind"],
        "status": job["status"],
        "created_at": job["created_at"],
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "result": result,
        "error": job.get("error"),
    }


class BoundedJobQueue:
    def __init__(
        self,
        *,
        max_workers: int = 1,
        max_pending: int = 4,
        max_history: int = 500,
        store=None,
    ):
        self.max_pending = max(1, int(max_pending))
        self.max_history = max(20, int(max_history))
        self._store = store
        self._queue: queue.Queue = queue.Queue(maxsize=self.max_pending)
        self._jobs: dict[str, dict] = {}
        self._lock = threading.RLock()
        self._workers = []

        if self._store is not None:
            # The store marks jobs that were queued/running at process shutdown as
            # failed. Never re-enqueue stale callables or claim they resumed.
            restored = self._store.list(limit=self.max_history)
            self._jobs = {job["job_id"]: job for job in restored}

        for index in range(max(1, int(max_workers))):
            worker = threading.Thread(target=self._work, name=f"audiolab-job-worker-{index + 1}", daemon=True)
            worker.start()
            self._workers.append(worker)

    def _persist_locked(self, job: dict) -> None:
        if self._store is None:
            return
        try:
            self._store.save(dict(job))
        except Exception:
            logging.exception("Audiolab could not persist job %s", job.get("job_id"))

    def submit(self, kind: str, function, *args, **kwargs) -> str:
        job_id = uuid.uuid4().hex
        job = {
            "job_id": job_id,
            "kind": str(kind),
            "status": "queued",
            "created_at": _now(),
            "started_at": None,
            "finished_at": None,
            "result": None,
            "error": None,
        }
        with self._lock:
            self._prune_locked()
            self._jobs[job_id] = job
            if self._store is not None:
                # Do not accept work if the durable history write fails.
                try:
                    self._store.save(dict(job))
                except Exception:
                    self._jobs.pop(job_id, None)
                    raise
            try:
                self._queue.put_nowait((job_id, function, args, kwargs))
            except queue.Full as exc:
                self._jobs.pop(job_id, None)
                if self._store is not None:
                    self._store.delete(job_id)
                raise QueueFullError("Audiolab's audio job queue is full. Wait for a job to finish and retry.") from exc
        return job_id

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def list_jobs(self, *, limit: int = 50, status: str | None = None) -> list[dict]:
        limit = min(100, max(1, int(limit)))
        with self._lock:
            jobs = [
                dict(job) for job in self._jobs.values()
                if not status or job["status"] == status
            ]
        jobs.sort(key=lambda job: job["created_at"], reverse=True)
        return jobs[:limit]

    def _work(self):
        while True:
            job_id, function, args, kwargs = self._queue.get()
            with self._lock:
                job = self._jobs.get(job_id)
                if job is not None:
                    job["status"] = "running"
                    job["started_at"] = _now()
                    self._persist_locked(job)
            try:
                result = function(*args, **kwargs)
            except Exception as exc:
                with self._lock:
                    job = self._jobs.get(job_id)
                    if job is not None:
                        job["status"] = "failed"
                        job["error"] = (str(exc).strip() or "Audio job failed.")[:500]
                        job["finished_at"] = _now()
                        self._persist_locked(job)
            else:
                with self._lock:
                    job = self._jobs.get(job_id)
                    if job is not None:
                        job["status"] = "succeeded"
                        job["result"] = result
                        job["finished_at"] = _now()
                        self._persist_locked(job)
            finally:
                self._queue.task_done()
                with self._lock:
                    self._prune_locked()

    def _prune_locked(self):
        if len(self._jobs) < self.max_history:
            return
        completed = sorted(
            (job for job in self._jobs.values() if job["status"] in {"succeeded", "failed"}),
            key=lambda job: job["finished_at"] or job["created_at"],
        )
        while len(self._jobs) >= self.max_history and completed:
            expired_id = completed.pop(0)["job_id"]
            self._jobs.pop(expired_id, None)
            if self._store is not None:
                try:
                    self._store.delete(expired_id)
                except Exception:
                    logging.exception("Audiolab could not prune job %s", expired_id)

    def stats(self) -> dict:
        with self._lock:
            statuses = {name: 0 for name in ("queued", "running", "succeeded", "failed")}
            for job in self._jobs.values():
                statuses[job["status"]] = statuses.get(job["status"], 0) + 1
            return {
                "mode": "in_process",
                "workers": len(self._workers),
                "max_pending": self.max_pending,
                "pending_slots_used": self._queue.qsize(),
                "jobs_in_memory": len(self._jobs),
                "counts": statuses,
                "durability": (
                    "Job history is stored in local SQLite. Queued/running work is marked interrupted "
                    "after restart; inference does not resume and render artifacts remain temporary."
                    if self._store is not None
                    else "Job state is cleared when the process restarts; completed render artifacts are temporary files."
                ),
            }

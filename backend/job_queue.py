"""Bounded in-process worker queue for long-running local audio jobs.

This is intentionally single-process. Multi-replica deployments should replace it with
a durable external broker and shared artifact storage before scaling horizontally.
"""
from datetime import datetime, timezone
import queue
import threading
import uuid


class QueueFullError(RuntimeError):
    """Raised when the bounded pending queue cannot accept another task."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BoundedJobQueue:
    def __init__(self, *, max_workers: int = 1, max_pending: int = 4, max_history: int = 500):
        self.max_pending = max(1, int(max_pending))
        self.max_history = max(20, int(max_history))
        self._queue: queue.Queue = queue.Queue(maxsize=self.max_pending)
        self._jobs: dict[str, dict] = {}
        self._lock = threading.RLock()
        self._workers = []
        for index in range(max(1, int(max_workers))):
            worker = threading.Thread(target=self._work, name=f"audiolab-job-worker-{index + 1}", daemon=True)
            worker.start()
            self._workers.append(worker)

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
            try:
                self._queue.put_nowait((job_id, function, args, kwargs))
            except queue.Full as exc:
                self._jobs.pop(job_id, None)
                raise QueueFullError("Audiolab's audio job queue is full. Wait for a job to finish and retry.") from exc
        return job_id

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def _work(self):
        while True:
            job_id, function, args, kwargs = self._queue.get()
            with self._lock:
                job = self._jobs.get(job_id)
                if job is not None:
                    job["status"] = "running"
                    job["started_at"] = _now()
            try:
                result = function(*args, **kwargs)
            except Exception as exc:
                with self._lock:
                    job = self._jobs.get(job_id)
                    if job is not None:
                        job["status"] = "failed"
                        job["error"] = (str(exc).strip() or "Audio job failed.")[:500]
                        job["finished_at"] = _now()
            else:
                with self._lock:
                    job = self._jobs.get(job_id)
                    if job is not None:
                        job["status"] = "succeeded"
                        job["result"] = result
                        job["finished_at"] = _now()
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
            self._jobs.pop(completed.pop(0)["job_id"], None)

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
                "durability": "Job state is cleared when the process restarts; completed render artifacts are temporary files.",
            }

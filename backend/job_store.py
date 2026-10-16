"""SQLite persistence for Audiolab's local audio-job history.

Job metadata is durable; Python callables and in-flight inference are not. A process
restart marks unfinished work as interrupted rather than pretending it resumed.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PersistentJobStore:
    """Small local SQLite store with bounded, JSON-serializable job records."""

    def __init__(self, path: str | Path, *, max_history: int = 500):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_history = max(20, int(max_history))
        self._lock = threading.RLock()
        with self._connection() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS audio_jobs (
                    job_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    result_json TEXT,
                    error TEXT
                )
                """
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_audio_jobs_created ON audio_jobs(created_at DESC)"
            )
            # Queued callables/uploads are intentionally not persisted. Mark them as
            # interrupted so clients can see what happened and submit them again.
            db.execute(
                """
                UPDATE audio_jobs
                SET status = 'failed',
                    error = 'Backend restarted before this job completed. Please submit it again.',
                    finished_at = ?
                WHERE status IN ('queued', 'running')
                """,
                (_now(),),
            )
            self._prune(db)

    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout = 10000")
        return db

    @contextmanager
    def _connection(self):
        db = self._connect()
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _encode_result(result):
        if result is None:
            return None
        return json.dumps(result, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _decode(row):
        return {
            "job_id": row["job_id"],
            "kind": row["kind"],
            "status": row["status"],
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "error": row["error"],
        }

    def save(self, job: dict) -> None:
        result_json = self._encode_result(job.get("result"))
        with self._lock, self._connection() as db:
            db.execute(
                """
                INSERT INTO audio_jobs
                    (job_id, kind, status, created_at, started_at, finished_at, result_json, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    kind=excluded.kind,
                    status=excluded.status,
                    created_at=excluded.created_at,
                    started_at=excluded.started_at,
                    finished_at=excluded.finished_at,
                    result_json=excluded.result_json,
                    error=excluded.error
                """,
                (
                    job["job_id"], job["kind"], job["status"], job["created_at"],
                    job.get("started_at"), job.get("finished_at"), result_json, job.get("error"),
                ),
            )
            self._prune(db)

    def delete(self, job_id: str) -> None:
        with self._lock, self._connection() as db:
            db.execute("DELETE FROM audio_jobs WHERE job_id = ?", (job_id,))

    def get(self, job_id: str) -> dict | None:
        with self._lock, self._connection() as db:
            row = db.execute("SELECT * FROM audio_jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._decode(row) if row else None

    def list(self, *, limit: int = 50, status: str | None = None) -> list[dict]:
        limit = min(100, max(1, int(limit)))
        with self._lock, self._connection() as db:
            if status:
                rows = db.execute(
                    "SELECT * FROM audio_jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM audio_jobs ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
        return [self._decode(row) for row in rows]

    def _prune(self, db) -> None:
        db.execute(
            """
            DELETE FROM audio_jobs
            WHERE job_id IN (
                SELECT job_id FROM audio_jobs
                ORDER BY
                    CASE WHEN status IN ('queued', 'running') THEN 1 ELSE 0 END,
                    COALESCE(finished_at, created_at) DESC
                LIMIT -1 OFFSET ?
            )
            """,
            (self.max_history,),
        )

    def status(self) -> dict:
        with self._lock, self._connection() as db:
            count = db.execute("SELECT COUNT(*) FROM audio_jobs").fetchone()[0]
        return {
            "enabled": True,
            "backend": "sqlite",
            "records": count,
            "max_history": self.max_history,
            "unfinished_jobs_resume": False,
            "note": "Job history persists locally; in-flight inference is marked interrupted after restart.",
        }

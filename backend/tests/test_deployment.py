from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deployment import SlidingWindowRateLimiter, authorize_request, is_loopback_client
from job_queue import BoundedJobQueue, QueueFullError


def test_local_only_access_allows_loopback_but_blocks_remote_without_key():
    assert is_loopback_client("127.0.0.1")
    assert is_loopback_client("::1")
    assert not is_loopback_client("192.168.1.20")
    assert authorize_request(
        path="/generate", method="POST", client_host="127.0.0.1",
        configured_api_key="",
    )[0]
    allowed, message = authorize_request(
        path="/generate", method="POST", client_host="203.0.113.8",
        configured_api_key="",
    )
    assert not allowed
    assert "Remote API access is disabled" in message


def test_api_key_required_for_remote_routes_but_health_is_public():
    assert authorize_request(
        path="/health", method="GET", client_host="203.0.113.8",
        configured_api_key="secret",
    )[0]
    assert not authorize_request(
        path="/generate", method="POST", client_host="203.0.113.8",
        configured_api_key="secret", supplied_api_key="wrong",
    )[0]
    assert authorize_request(
        path="/generate", method="POST", client_host="203.0.113.8",
        configured_api_key="secret", supplied_api_key="secret",
    )[0]


def test_sliding_window_rate_limiter_resets_after_window():
    limiter = SlidingWindowRateLimiter()
    assert limiter.allow("client", "general", limit=2, window_seconds=10, now=1)[0]
    assert limiter.allow("client", "general", limit=2, window_seconds=10, now=2)[0]
    allowed, retry = limiter.allow("client", "general", limit=2, window_seconds=10, now=3)
    assert not allowed and retry > 0
    assert limiter.allow("client", "general", limit=2, window_seconds=10, now=12)[0]


def test_bounded_job_queue_runs_task_and_exposes_status():
    queue = BoundedJobQueue(max_workers=1, max_pending=2)
    job_id = queue.submit("test", lambda value: {"answer": value}, 42)
    deadline = time.monotonic() + 2
    job = queue.get(job_id)
    while job and job["status"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.01)
        job = queue.get(job_id)
    assert job["status"] == "succeeded"
    assert job["result"] == {"answer": 42}
    assert job["finished_at"]


def test_bounded_job_queue_records_safe_failure_state():
    queue = BoundedJobQueue(max_workers=1, max_pending=2)
    job_id = queue.submit("test", lambda: (_ for _ in ()).throw(ValueError("bad input")))
    deadline = time.monotonic() + 2
    job = queue.get(job_id)
    while job and job["status"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.01)
        job = queue.get(job_id)
    assert job["status"] == "failed"
    assert job["error"] == "bad input"

# Audiolab deployment and Phase 9 operations

## Security model

Audiolab is local-first. The backend is **loopback-only by default**: when `AUDIOLAB_API_KEY` is unset, non-loopback clients are denied access to API routes. `GET /health` remains available for a minimal health probe. Do not expose the unauthenticated local backend directly to the internet.

For a trusted server-to-server integration, set a strong random `AUDIOLAB_API_KEY` in the backend's secret manager and send it as either `X-Audiolab-API-Key` or `Authorization: Bearer <key>`. Never commit the key or embed it in browser JavaScript, a public static site, query strings, or logs. A public browser product needs a real user-authentication gateway that keeps service credentials server-side; CORS is not authentication.

When deploying a container with `AUDIOLAB_HOST=0.0.0.0`, configure the API key and firewall/network policy. Keep TLS at the trusted reverse proxy/load balancer. Expose only the routes required by the gateway; restrict `/docs`, `/redoc`, and `/openapi.json` to trusted operators where practical.

## Usage and resource limits

| Environment variable | Default | Purpose |
| --- | ---: | --- |
| `AUDIOLAB_API_KEY` | unset | Enables API-key authorization for non-health routes; without it, remote clients are blocked |
| `AUDIOLAB_MAX_UPLOAD_MB` | `100` | Maximum uploaded audio size per file |
| `AUDIOLAB_MAX_TEXT_LENGTH` | `10000` | Maximum validated text length |
| `AUDIOLAB_REQUESTS_PER_MINUTE` | `120` | Per-client general request limit |
| `AUDIOLAB_HEAVY_REQUESTS_PER_MINUTE` | `8` | Per-client limit for expensive inference/job submissions |
| `AUDIOLAB_MAX_CONCURRENT_JOBS` | `1` | Concurrent direct heavy requests per process |
| `AUDIOLAB_JOB_WORKERS` | `1` | Worker threads for queued timed-dubbing tasks |
| `AUDIOLAB_JOB_QUEUE_SIZE` | `4` | Maximum waiting queued tasks, in addition to active work |\n| `AUDIOLAB_JOB_DB` | `backend/audiolab-job-history.sqlite3` | Local SQLite path for bounded job metadata history |

Rate limits and job state are process-local. If the application is restarted, in-memory job state is lost. The job queue is deliberately bounded to protect local CPU/GPU memory and prevent unbounded backlog.

## Queued timed-dubbing API

- `POST /jobs/dub-transcribe` — multipart form with `source_file` and optional `source_language`; returns HTTP 202 with a `job_id`.
- `POST /jobs/dub-render` — multipart form with `target_file`, `segments_json`, `target_language`, `ref_text`, and `consent=true`; returns HTTP 202 with a `job_id`.
- `GET /jobs/{job_id}` — poll `queued`, `running`, `succeeded`, or `failed` status. Successful transcription returns reviewed/editable timestamped segments. Successful rendering returns a download URL.
- `GET /jobs/{job_id}/download` — download the render ZIP. The temporary archive is deleted after a successful response; download it before submitting the same job again.

A full queue returns HTTP 429 with a retry hint. Job IDs are random, but authorization is still required for remote access. Keep the API key private and do not share job IDs as if they were access credentials.

## Persistent job history (Phase 10)\n\n- `GET /jobs?limit=50` lists recent jobs; optional `status` filters to `queued`, `running`, `succeeded`, or `failed`. The limit is clamped to 1–100.\n- Job metadata is stored in a local SQLite file (default `backend/audiolab-job-history.sqlite3`, ignored by Git). Set `AUDIOLAB_JOB_DB` to choose another writable path. Back up this file only if you want to retain local job history.\n- On process restart, persisted `queued` and `running` records are marked failed with a restart message. Audiolab does not resume inference because uploaded arguments/callables are not persisted. Submit the job again.\n- Completed render archives are still temporary files and are not guaranteed to survive cleanup, download, or artifact expiry. The API never returns internal filesystem paths.\n- History is bounded to 500 records by default. This SQLite store does not make the worker queue distributed or safe for multi-replica deployment.\n\n## Model management and recovery

- `GET /models` reports dependency/model readiness without forcing large model downloads.
- `GET /health` reports model state, configured limits, access mode, and queue counts. API health does not guarantee that weights have loaded or that inference will succeed.
- Each response includes an `X-Request-ID`; include it when diagnosing a failure. HTTP 429 means a rate or concurrency limit was reached; wait and retry. HTTP 403 means access is not authorized. A failed queued job returns a bounded error message in its status payload.
- Keep model checkpoints outside Git and provision cache/disk capacity before enabling GPU inference. Restarting the process clears in-memory queue state; stale temporary artifacts are cleaned on startup.

## Production scaling boundary

This release provides a bounded **single-process** queue, not a distributed durable queue. Do not scale it to multiple replicas expecting shared job status or artifact paths. Before horizontal scaling, replace the in-process queue with a durable broker (for example Redis/Celery or a managed queue), persist job metadata, store artifacts in shared object storage with expiry, add user-scoped authorization/quotas, and configure observability and cleanup policies. The public UI should call a trusted gateway; it should not connect to a raw local inference server or carry a shared backend secret.


## Job history workspace (Phase 11)

The Studio **History** page displays browser-local generation entries separately from backend jobs. It fetches `GET /jobs?limit=50` from the configured local API, and supports filters for `queued`, `running`, `succeeded`, and `failed`. A failed API request is shown as an explicit unavailable state with a retry control; the UI does not fabricate history.

Successful dubbing-render jobs expose a download link. The download response is temporary and the backend deletes the archive after serving it, so save the ZIP before leaving the page. The backend history remains metadata-only and does not guarantee the archive survives a restart or a previous download.

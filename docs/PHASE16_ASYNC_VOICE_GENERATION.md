# Phase 16 — Asynchronous real voice generation

The Studio's local Generate workflow now submits IndicF5 work to the existing bounded background worker instead of keeping the browser request open for the full model inference.

## Workflow

1. The browser posts the script, selected language, exact reference transcript, and authorized reference audio to `POST /jobs/generate`.
2. FastAPI validates the text/language and saves the upload to a temporary local file.
3. The bounded worker queue returns a stable `job_id`; the browser polls `GET /jobs/{job_id}`.
4. The worker cleans the reference audio, loads/reuses IndicF5, runs real model inference, and validates that the output is a readable non-empty WAV.
5. Job metadata is persisted in the existing local SQLite history. The API response contains only a download URL and safe metadata, never a filesystem path.
6. The browser downloads the WAV through `GET /jobs/{job_id}/download`, validates the RIFF/WAVE header, then applies the existing browser-side delivery-style processing and playback/download UI.

The synchronous `POST /generate` endpoint remains available for compatibility. The browser's local Studio path uses the queued endpoint. The hosted public path remains the existing Hugging Face Space integration; no local backend URL or API secret is exposed to Vercel.

## Windows verification

After pulling the branch/merged changes, start Audiolab using `START-AUDIOLAB.bat`. Open `http://127.0.0.1:5500/studio.html`, go to Generate, select a saved/uploaded voice reference, confirm permission to use it, enter the exact reference transcript and Tamil text, then click Generate.

Verify all of the following:

- The status moves through queued/running and eventually succeeds or shows a real error.
- The result plays and downloads as a valid WAV.
- `GET http://127.0.0.1:8000/jobs?limit=10` shows the completed `voice-generate` job.
- The public job response does not include `artifact_path` or other local filesystem paths.
- A second generation can reuse the already-loaded model.
- If IndicF5 dependencies, Hugging Face access, model weights, or the reference audio are invalid, the UI shows a failure instead of a fake success.

Run lightweight checks from the repository root:

```powershell
python -m pytest -q backend/tests
```

This automated change adds async job lifecycle and artifact validation; it does not itself prove that IndicF5 can load or produce high-quality Tamil speech on a particular Windows machine. Real model verification still requires the above local smoke test with a permitted voice reference.

# Phase 15 — Real inference validation

Phase 15 strengthens the local end-to-end smoke test so a successful HTTP response is not mistaken for a successful audio workflow. It stays local-first and uses Python's standard library; it does not install dependencies or download model weights.

## Before a transcription run

Start Audiolab with `START-AUDIOLAB.bat`, then run this from a second PowerShell window at the repository root:

```powershell
python scripts/audiolab_e2e_smoke.py --transcribe-audio "C:\path\to\short-speech.wav" --timeout 1800
```

The smoke test now validates that the input exists, has a supported extension, is non-empty, and is below the 100 MiB preflight limit. WAV inputs are decoded by Python's standard-library WAV reader to confirm valid audio parameters and nonzero frames before upload. Other supported compressed formats receive extension/size/non-empty checks; their full decoding is left to the backend.

## What a passing transcription means

- The local API health and job-history endpoints respond.
- The real audio is submitted to `POST /jobs/dub-transcribe`.
- The queue reports progress while the job is running.
- The completed result contains non-empty segments with finite, ordered, non-negative timestamps and non-empty text.
- The completed job appears in local job history.

A backend failure is surfaced with its returned error text. Missing `faster-whisper`, model download/load errors, and no-speech cases should produce actionable errors from the backend; this test does not silently substitute synthetic inference.

## Validate a real dubbing render

Only use a target voice recording you have permission to use. Follow the manifest instructions in [Phase 13](PHASE13_E2E.md), then run:

```powershell
python scripts/audiolab_e2e_smoke.py --render-manifest ".\render-manifest.json" --confirm-voice-rights --timeout 1800
```

The downloaded ZIP is inspected beyond its signature: the WAV must decode and contain frames, the SRT must contain a timestamped cue, and the JSON must parse and contain valid timed segments. The validated archive is saved under `audiolab-e2e-results`.

## Tests and boundaries

Run lightweight tests with:

```powershell
python -m pytest -q backend/tests
```

CI uses synthetic fixtures and does not download model weights. A passing CI run verifies validation behavior, not the quality of actual IndicF5/faster-whisper inference. Model weights may require first-run internet access and disk space; CPU inference may be slow. Keep the backend bound to loopback and never expose an unauthenticated local inference API publicly.

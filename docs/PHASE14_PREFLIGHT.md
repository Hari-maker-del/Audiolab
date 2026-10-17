# Phase 14 — Local readiness diagnostics

The preflight script helps diagnose common setup issues before spending time downloading models or generating audio. It does not install packages, download weights, or submit audio.

## Windows quick start

1. Start Audiolab using `START-AUDIOLAB.bat`.
2. Open PowerShell at the repository root.
3. Run:

```powershell
python scripts/audiolab_preflight.py --project-root .
```

To save machine-readable output for debugging:

```powershell
python scripts/audiolab_preflight.py --project-root . --json
```

If you use the backend virtual environment directly, you can run the script with that Python executable:

```powershell
.\backend\.venv\Scripts\python.exe scripts\audiolab_preflight.py --project-root .
```

## What it checks

- Python version and operating system.
- Required API distributions (FastAPI, Uvicorn, and multipart upload support).
- Presence/version of optional audio packages that may be used by additional features.
- Free disk space at the project location.
- Whether the project's backend virtual environment exists.
- Local API health and available feature diagnostics.
- Whether the IndicF5 engine is already loaded, without incorrectly treating its normal lazy loading as a failure.

The API check only accepts a loopback HTTP URL such as `http://127.0.0.1:8000`. It does not probe a public endpoint or put an API key into a URL.

## Interpreting results

- `FAIL`: a required dependency or local API check failed. Follow the printed next step and rerun.
- `WARN`: optional packages may be missing or disk space is low. Only install dependencies for the features you intend to use.
- `INFO model_loaded`: IndicF5 normally loads on the first generation request. This is informational, not proof of failure.
- `PASS`: the individual preflight check passed.

Preflight is diagnostic only. A healthy API and installed packages do not prove that model weights can load or that inference succeeds. For actual transcription/render verification, use the Phase 13 instructions in [PHASE13_E2E.md](PHASE13_E2E.md) with your own audio input.

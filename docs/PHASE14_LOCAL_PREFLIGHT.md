# Phase 14 — Local readiness diagnostics

The preflight command diagnoses common setup problems before you spend time downloading models or starting a long audio job. It is read-only: it does not install dependencies, fetch model weights, modify settings, or submit audio.

## Run it on Windows

Open PowerShell at the Audiolab repository root:

\`\`\`powershell
python scripts/audiolab_preflight.py
\`\`\`

If the API is already running on the default local address, the report checks:
- Python version and operating system
- Required API packages and optional audio feature packages
- Free disk space and the expected project virtual environment
- The local \`/health\` endpoint, job queue, device, model-load state, and available feature status

The default API URL is \`http://127.0.0.1:8000\`. The tool refuses non-loopback hosts and does not send an API key. Keep your unauthenticated local inference server bound to loopback.

## Machine-readable report

\`\`\`powershell
python scripts/audiolab_preflight.py --json
\`\`\`

You can save it locally for troubleshooting:

\`\`\`powershell
python scripts/audiolab_preflight.py --json | Out-File -Encoding utf8 audiolab-preflight.json
\`\`\`

Do not share reports without reviewing them first. They include local paths, package versions, and environment details.

## Interpret the result

- **PASS**: the check looks healthy.
- **WARN**: an optional feature package is missing, the virtual environment is absent, or disk space is low. Install only what you need.
- **FAIL**: a required API package is missing, Python is too old, or the local API cannot be reached/does not report healthy.
- **INFO**: context rather than a failure. In particular, IndicF5 being \`not_loaded\` at startup is expected because it loads on first generation.

Preflight is not an inference benchmark. A successful health check does not prove the model can load on your GPU/CPU or generate valid audio. For that, run the Phase 13 smoke test with an actual short speech file, then optionally a permitted target voice reference and render manifest. See [Phase 13 E2E](PHASE13_E2E.md).


## Input validation

The preflight rejects non-finite or negative disk-space thresholds and non-positive/non-finite API timeouts. This keeps diagnostic settings predictable and prevents malformed CLI options from producing misleading reports.

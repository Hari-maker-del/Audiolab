# 🎙️ Audiolab — IndicF5 Voice Studio

**Your voice. Your language. Your sound.**

Audiolab is a Tamil-first, Indian-language voice generation studio built around AI4Bharat IndicF5, with a warm **Turmeric × Malt** interface inspired by the Stitch design.

## What is included

- Production-style responsive frontend in `frontend/`
- Turmeric × Malt design system
- Studio dashboard
- Voice profile workflow
- Reference upload / microphone recording
- Reference quality analysis
- Exact reference transcript conditioning
- Tamil-first generation studio
- Tamil / Tanglish input UI modes
- Generation history stored locally in the browser
- Audio tools/model/settings screens
- FastAPI endpoints for frontend integration
- Original Gradio studio retained at `/legacy`
- Local IndicF5 inference
- CUDA PyTorch setup for supported NVIDIA GPUs
- One-click Windows local launcher

## Phase 15 — Real inference verification

The local end-to-end smoke test now checks input audio before upload and validates actual transcription timestamps/text. Render exports are checked for a readable WAV with frames, timestamped SRT cues, and valid timed segment metadata. See [Phase 15 instructions](docs/PHASE15_REAL_INFERENCE_VALIDATION.md). These checks do not claim model inference works until you run them against your local model setup.

## Web entry points

- `frontend/index.html`: public 3D marketing landing page.
- `frontend/studio.html`: Audiolab's existing audio workspace.
- `frontend/landing.html`: standalone landing-page preview/alias.

The landing page uses a dependency-free, interactive Canvas-based 3D-style audio sphere and responsive CSS depth effects. The landing page is static; AI conversion still requires the configured local backend and model files.

## Architecture

```text
Stitch-inspired frontend
        ↓
FastAPI (127.0.0.1:8000)
        ↓
Reference cleanup + quality analysis
        ↓
AI4Bharat IndicF5
        ↓
Vocos
        ↓
WAV output
```

## Run locally on Windows

Python 3.11.x is recommended.

### One-click start

Double-click:

`START-AUDIOLAB.bat`

Or run:

```powershell
.\START-AUDIOLAB.bat
```

The launcher starts:

- UI: `http://127.0.0.1:5500`
- API: `http://127.0.0.1:8000/health`

### Manual setup

```powershell
.\backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python backend\server.py
```

In another PowerShell window:

```powershell
python -m http.server 5500 --directory frontend
```

Then open `http://127.0.0.1:5500`.

## Hugging Face authentication

IndicF5 requires Hugging Face access. Log in before the first model load:

```powershell
python -m huggingface_hub.commands.huggingface_cli login
```

Keep your token private and never commit it to GitHub.

## Optional voice-to-voice conversion

Audiolab now includes an optional **OpenVoice V1 ToneColorConverter** integration for converting an existing performance toward a target reference voice. This is separate from IndicF5 text-to-speech. It may change the timing, pitch, pronunciation, and emotional delivery; compare the result with the source recording.

After running `START-AUDIOLAB.bat` once and ensuring `backend\.venv` exists, run this from the repository root in PowerShell:

```powershell
.\scripts\setup-voice-conversion.ps1
```

The setup script installs optional conversion dependencies and downloads the OpenVoice V1 checkpoints into `backend/models/openvoice_v1`. The model directory is ignored by Git and must stay out of source control. This download requires internet and disk space. The default setup uses local inference and no paid API; CPU inference may be slow.

Voice Convert is available in the Studio dashboard when the local FastAPI backend is running. Reference audio saved in the Voices library is stored in the current browser's IndexedDB; it is not synced between different browser origins or devices. The Models page reports whether the local conversion package and checkpoint files are present. Voice conversion has **not** been declared verified until a real source/target pair is converted successfully on the user's machine.

## API

### Health

`GET /health`

### Analyze a reference

`POST /analyze`

Multipart field:

`file`

### Generate speech

`POST /generate`

Multipart fields:

- `text`
- `language`
- `ref_text`
- `file`

The endpoint returns a WAV file when generation succeeds.

### Voice conversion

`POST /voice-convert`

Multipart fields:

- `source_file`: original voice-over audio
- `target_file`: target reference voice audio
- `consent`: `true` after confirming permission to use both voices

Returns the converted WAV only when real OpenVoice inference succeeds. `GET /models` reports the actual local model state.

The browser frontend uses `/api/*` paths locally and automatically bridges them to the FastAPI service on port `8000`.

## Indian languages

Tamil, Telugu, Malayalam, Hindi, Kannada, Bengali, Gujarati, Marathi, Odia, Punjabi and Assamese.

Only languages actually supported by the installed model should be presented as available.

## Privacy

Reference recordings are not committed to this repository. Keep personal voice samples local. Browser-side voice profiles/history are stored locally in the user's browser.

## Responsible use

Use only voices you own or have explicit permission to clone. Do not use the project for impersonation, fraud, deceptive identity claims, or unauthorized voice cloning.

Official model project: https://github.com/AI4Bharat/IndicF5

## Phase 2 — Local speech-to-text and reusable voices

### Optional local transcription (₹0, runs on your computer)

Speech-to-text uses the optional `faster-whisper` package; it is not installed by the core TTS requirements.

From the repository root in PowerShell:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-speech.txt
```

Restart Audiolab, open the Studio, select a voice reference, then use **Transcribe reference audio** to fill the reference transcript. Review and correct the transcript before generating. The first transcription downloads the selected Whisper model (default: `small`) and needs internet/disk space; inference then runs locally. To use a smaller model, set `AUDIOLAB_STT_MODEL=base` in the backend environment before starting the server. CPU transcription may be slow.

- API: `POST /transcribe` with multipart `file` and optional `language`.
- Status: `GET /health` includes `speech_to_text`; `GET /models` reports the optional model state.
- Language metadata: `GET /languages`.

### Reusable voice profiles

Voice profiles are stored in browser IndexedDB, including the actual reference-audio bytes. Use **Save Voice Profile** to persist a profile and select it from the Generate page or the voice library to load its recording. Profiles are local to the browser and device; they are not cloud-synced. Existing profiles created before Phase 2 may contain metadata only and need their reference audio uploaded and saved again.

### Language behavior

Audiolab validates the selected language against the IndicF5 language allow-list. The current IndicF5 wrapper takes text, reference audio, and the exact reference transcript; it does not expose a separate language-token argument. Text/script and the reference guide multilingual output, so choose the correct language and review the generated audio. A language dropdown alone cannot guarantee pronunciation quality.

## Phase 3 — Advanced audio creation and dubbing assist

### Local sound effects

Open Studio → **Tools** → Sound effects generator. The backend's `POST /sound-effects` endpoint creates WAV files locally using NumPy/SciPy DSP. Available effects: whoosh, impact, riser, rain texture, ambient drone, laser, and chime. Duration is limited to 0.25–20 seconds.

### Procedural music sketches

The `POST /music-sketch` endpoint creates short procedural beds (ambient, cinematic, lo-fi, pulse) without an external service. Duration is limited to 2–60 seconds. **This is a procedural sketch generator, not an AI music-generation model or a finished composition.**

### Dubbing assist

Studio → Tools → **Dubbing assist** takes an original recording, a reviewed target-language script, an authorized target-voice reference, and the exact target-reference transcript. It uses the optional local Whisper STT model to transcribe the original, then uses the existing IndicF5 backend to synthesize the supplied target-language script. It returns the WAV and exposes the detected source language/transcript as response metadata.

- The translation must be supplied and reviewed by the user; this phase does not translate automatically.
- It currently generates one target-language speech track, not word/sentence-aligned dubbing or original background-audio mixing.
- The target-language selector is validated, but the current IndicF5 wrapper does not pass a separate language-token argument. Listen and verify pronunciation.
- Install `backend/requirements-speech.txt` as described in Phase 2. Start the local backend before using these tools.
- The user must have rights to the source audio and permission to use the target voice. Voice recordings are uploaded to the local backend for processing and temporary files are cleaned after the request.

### Not yet delivered as AI-model features

Real generative music, source-separated vocal isolation, automatic translation, and a full conversational voice agent need separate model integrations and runtime tests. The procedural music bed and existing spectral noise-reduction filter must not be described as AI music generation or true vocal source separation.

## Phase 4 — Production readiness

### API documentation

Start the local backend and open:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`
- Health/model diagnostics: `http://127.0.0.1:8000/health` and `/models`

The health payload reports configured upload/text limits and model status separately from API availability. The backend uses a local-only bind by default. Do not expose it to the public internet without authentication, TLS, rate limiting, and an explicit deployment/security design.

### Reliability improvements

- Upload filenames no longer control temporary-file suffixes; unknown extensions are normalized.
- Merge/mix upload loops now clean up files even if a later upload fails.
- Startup cleanup removes Audiolab artifacts older than 24 hours left behind by an abrupt shutdown.
- API metadata identifies the local-first nature of inference and discloses that procedural sound/music are DSP.
- Tool results announce progress/errors, revoke replaced browser object URLs, and use the configured local API base.
- The Studio already includes responsive layouts for tablet/mobile widths (900px and 520px breakpoints).

### Automated tests

GitHub Actions compiles backend Python, checks frontend JavaScript syntax, and runs lightweight tests for every sound-effect type, every procedural music style, WAV validity, deterministic output, and invalid input limits. This test suite does not download IndicF5/OpenVoice/Whisper weights and does not replace Windows end-to-end listening tests.

To run the procedural tests locally:

```powershell
python -m pip install pytest numpy scipy soundfile
python -m pytest -q backend/tests
```

### Runtime acceptance checklist

- Open `/health`, `/docs`, and `/models`.
- Generate each sound effect and music sketch; play and download every WAV.
- Try invalid effect/style/duration values and verify a clear 400 error.
- Install optional STT and model files, then test transcription, IndicF5 generation, voice conversion, and dubbing with authorized recordings.
- On a phone-sized viewport, navigate Studio, Generate, Voices, History, Tools and Settings; check file selection, audio playback and downloads.
- Check browser storage quota, clear-data behavior, and recovery from an offline backend.

The source code and CI can validate deterministic DSP workflows. Actual AI model quality, Windows hardware compatibility, and full mobile-browser behavior still require local runtime verification.

## Phase 5 — Local AI vocal isolation

Audiolab now includes an optional source-separation workflow powered by **Demucs HTDemucs**. This is a real open-source audio-separation model, separate from the basic spectral noise-reduction filter.

### Enable the feature on Windows

From the repository root in PowerShell, after updating the project:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-separation.txt
```

Restart `START-AUDIOLAB.bat`, open the Studio → **Audio Studio / Tools** → **Vocal isolation**, select an audio file, confirm you have rights to process it, then click **Separate vocals and instrumental**.

- Endpoint: `POST /separate` with multipart `file`.
- The result is a ZIP containing `vocals.wav` and `instrumental.wav`.
- Status: `GET /health` and `GET /models` expose `demucs-htdemucs` package/model state without downloading weights.
- The first separation downloads the Demucs model weights. Internet access and disk space are needed for that first run.
- The backend automatically selects CUDA when PyTorch detects a supported NVIDIA GPU; otherwise it uses CPU. CPU inference can be slow, especially for long recordings.
- The default request timeout is 1,200 seconds. Override with `AUDIOLAB_SEPARATION_TIMEOUT_SECONDS` if needed. Shorter clips are easier to test.
- This is local inference; it does not call a paid cloud API. Demucs' output is an estimate and may contain bleed/artifacts depending on the recording.
- Install the optional package only when you want source separation; it is not added to the core TTS requirements.

The CI tests validate status reporting and output-file discovery. They do not install Demucs, download model weights, or prove real separation quality. Run a local test with a short recording and listen to both WAV stems.

## Phase 6 — Real AI text-to-music generation

Audiolab now has an optional **MusicGen Small** integration at `POST /music-generate`. Unlike the existing procedural music sketch tool, this endpoint loads an actual text-conditioned generative music model and produces a WAV from a natural-language prompt.

### Enable it on Windows

From the repository root in PowerShell:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-music.txt
```

Restart `START-AUDIOLAB.bat`, open Studio → **Audio Studio / Tools** → **Text to music**, describe the music, select a duration from 5–15 seconds, and generate.

- Model: `facebook/musicgen-small`.
- Endpoint: `POST /music-generate` with `prompt` and `duration` multipart fields.
- Output: downloadable WAV audio.
- Status: `GET /health` and `GET /models` report whether the dependencies/model are available or loaded without forcing a model download.
- First generation downloads model weights from Hugging Face (roughly 1 GB of model files; leave extra disk space for cache). Internet access is required for this first download.
- The backend chooses CUDA if PyTorch detects a compatible NVIDIA GPU, otherwise CPU. CPU generation can be very slow; 5–8 second clips are best for an initial test.
- This is local inference, not a paid hosted API. It is not included in the default core requirements.
- Requests are limited to 500 prompt characters and 5–15 seconds to reduce resource use. A single generation runs at a time.
- **License warning:** the upstream MusicGen Small model weights are licensed CC-BY-NC 4.0 (Creative Commons Attribution-NonCommercial 4.0). Treat this integration as non-commercial research/prototyping unless you obtain appropriate separate rights; do not assume it is cleared for commercial Audiolab use. See the [upstream model card](https://huggingface.co/facebook/musicgen-small) and review its current terms before distributing or monetizing generated output.

The CI tests check request validation and status reporting without downloading model weights. They do not prove successful inference or generated-audio quality on your machine.

## Phase 7 — Conversational voice agent

Audiolab now includes a local-first conversation endpoint at `POST /voice-agent` and a **Talk to Audiolab** card in Studio → Audio Studio / Tools.

### Try it on Windows

1. Pull the latest repository changes and restart `START-AUDIOLAB.bat`.
2. Open Studio → Audio Studio / Tools → **Talk to Audiolab**.
3. Type a request or upload a spoken request. The audio path uses the optional local faster-whisper dependency.
4. Audiolab identifies common intents (music generation, vocal isolation, speech generation, transcription, voice conversion, help) and returns guidance.
5. For a spoken reply, add an authorized voice-reference recording and its exact transcript. The reply is generated by IndicF5, so the core TTS model must be configured and load successfully.

Optional speech-recognition setup, if it is not already installed:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-speech.txt
```

### Honest scope and privacy

- Intent understanding currently uses local, explicit rule matching; it is **not** a general-purpose LLM and may fall back for requests it does not recognize.
- Speech input requires faster-whisper and its model weights; first use may download weights. Spoken output requires IndicF5 plus a voice reference and exact transcript.
- The client can retain its own conversation state, but this endpoint does not save conversation history server-side. Current release is request/response, not a continuous streaming voice call.
- Requests without a voice reference return a text reply as JSON. Requests with a permitted reference can return a generated WAV reply.
- Tests cover intent routing and response behavior without downloading speech or TTS model weights. Runtime voice interaction must still be verified on your computer.

## Phase 8 — Sentence-timed dubbing and subtitles

Studio → Tools → **Sentence-timed dubbing studio** provides a local dubbing-project workflow:

1. Upload the source recording and transcribe it with optional local faster-whisper. The API returns timestamped segments.
2. Edit the recognized source text, adjust each segment's start/end time, and enter the reviewed translation for every segment.
3. Use the live SRT preview to check translated text and subtitle timecodes before rendering. Invalid time ranges and obvious overlaps are rejected in the UI; the backend validates again.
4. Provide an authorized target voice reference and its exact transcript, then render with local IndicF5.
5. Download a ZIP containing `dubbed_voice.wav`, `subtitles.srt`, and `segments.json`. The JSON includes a per-segment fit report.

- API: `POST /dub-transcribe` creates timestamped source segments; `POST /dub-render` generates the timed track and exports SRT.
- This phase does not automatically translate text. Human review is required for every translated segment.
- Alignment uses speech-recognition timestamps. If a generated line is longer than its time slot, Audiolab may time-stretch it or trim it; pronunciation, pacing, and timing need listening review.
- The exported WAV is a dubbed voice track only. It does not include the original background audio, and it is not lip-sync.
- Model inference remains local and requires the optional faster-whisper setup plus a working IndicF5 environment. Runtime audio quality must be verified on the target machine.


## Phase 9 — Secure product and deployment foundation

Phase 9 adds a guarded API and bounded queue for long-running sentence-timed dubbing jobs.

- Remote API access is denied by default when no `AUDIOLAB_API_KEY` is configured; local loopback use continues to work. Health probes remain available.
- When configured, API clients authenticate with `X-Audiolab-API-Key` or a Bearer token. **Never place this shared key in browser JavaScript or a public static frontend.** A public browser app needs a trusted server-side gateway and user authentication.
- Per-client request limits, heavy-task limits, concurrent-work guards, request IDs, and upload-body limits reduce accidental overload.
- The timed dubbing studio now submits transcription and render jobs to a bounded worker queue, displays queued/running progress, and polls job status. Render archives are temporary and are removed after download.
- `GET /health` exposes access mode, configured limits, model readiness, and queue counts; `GET /models` remains the model/dependency status endpoint.
- The queue and rate limiter are process-local. Restarting the backend clears job state. This is a secure single-process baseline, not yet a horizontally scaled durable worker platform.

See [DEPLOYMENT.md](DEPLOYMENT.md) for environment variables, API usage, security rules, and the production scaling boundary. Do not expose the local backend directly to the public internet.


## Phase 10 — Persistent local job history and restart recovery

Phase 10 builds on the Phase 9 job queue by storing job records in a local SQLite database. The default database is `backend/audiolab-job-history.sqlite3`; it is ignored by Git and can be moved with the `AUDIOLAB_JOB_DB` environment variable.

- Completed, failed, and queued job metadata survives a backend restart.
- `GET /jobs?limit=50` lists recent jobs. Use `status=queued`, `running`, `succeeded`, or `failed` to filter. The limit is bounded to 100.
- `GET /jobs/{job_id}` continues to return an individual job; render results expose a download URL without exposing server filesystem paths.
- On restart, any queued or running job is marked **failed** with an explicit interruption message. Inference is not resumed because worker callables and upload arguments are not persisted.
- Job history is local and bounded to 500 records by default. The actual render ZIP remains a temporary artifact and can expire or be removed after download.
- `GET /health` reports whether SQLite history is enabled and clarifies that job history persists while in-flight work does not resume.

This is durable **job metadata**, not a distributed queue or durable artifact store. Keep the backend local unless you have implemented the Phase 9 server-side gateway and security controls. Tests cover restart recovery, completed-result persistence, status filtering, and retention pruning; model inference still needs a real local runtime test.


## Phase 11 — Job history workspace and safer API responses

The studio History page now brings together two distinct sources: browser-local generated-audio entries and persistent local-backend dubbing jobs. Backend history can be refreshed and filtered by queued, running, succeeded, or failed status. Failed jobs show their recorded error; completed dubbing exports provide a download link.

- The backend queue and single-job endpoints share a response serializer so a completed render exposes a download URL, not its local filesystem path.
- UI connection failures are shown explicitly with a retry action; the page does not fabricate job records when the local backend is unavailable.
- Automated tests cover public render-path redaction, transcription result visibility, and failed-job error display.
- The static-check workflow checks the edited frontend JavaScript syntax and runs the backend tests. Real model inference remains a separate runtime verification step.


## Phase 12 — End-to-end job reliability

- Added a shared browser job client for status polling and render downloads.
- Temporary network failures and HTTP 429/5xx responses retry with bounded backoff; authorization and other terminal errors are surfaced immediately.
- Polling has a deadline, validates job-status payloads, and reports retries to the user rather than failing at the first connection blip.
- Render downloads must have a ZIP signature; successful HTML/error pages are rejected instead of being presented as audio exports.
- Added dependency-free Node tests for success/failure states, transient errors, timeout, URL validation, and ZIP integrity. GitHub Actions now runs these tests.
- This validates workflow reliability with mocked HTTP responses. It does not replace a real browser/backend test using model weights and actual audio files.


## Phase 13 — Local end-to-end verification

Run `python scripts/audiolab_e2e_smoke.py` while the FastAPI backend is running on `127.0.0.1` to verify health and persisted job history. Add `--transcribe-audio <file>` to submit a real local transcription job, or `--render-manifest <json> --confirm-voice-rights` to render a real dubbing project and validate/download its ZIP. Full Windows commands and the manifest format are in [docs/PHASE13_E2E.md](docs/PHASE13_E2E.md).

The smoke client rejects non-loopback hosts. CI uses a synthetic local HTTP fixture to test the workflow and archive checks; this is not evidence that model inference succeeded on a particular computer. A real model-backed run must be executed on the local machine with actual audio inputs.


## Phase 14 — Local readiness preflight

Run `python scripts/audiolab_preflight.py` before a model-backed test to check Python, required API packages, optional audio packages, free disk space, the project virtual environment, and the loopback API health/feature status. Use `--json` for machine-readable output. It is read-only and does not install packages, download models, or submit audio. The API URL is restricted to loopback. See [docs/PHASE14_LOCAL_PREFLIGHT.md](docs/PHASE14_LOCAL_PREFLIGHT.md).

A successful preflight is not proof that model inference works; use the Phase 13 smoke test with real audio for that final check.

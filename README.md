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

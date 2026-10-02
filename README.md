# 🎙️ Audiolab — IndicF5 Voice Studio

**Your voice. Your language. Your sound.**

Audiolab is a Tamil-first, Indian-language voice generation studio built around AI4Bharat IndicF5, with a warm **Turmeric × Malt** interface inspired by the Stitch design.

## What is now included

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

## Architecture

```text
Stitch-inspired frontend
        ↓
FastAPI
        ↓
Reference cleanup + quality analysis
        ↓
AI4Bharat IndicF5
        ↓
WAV output
```

## Run locally

Recommended Python: 3.10.

```powershell
.\scripts\setup_windows.ps1
huggingface-cli login
.\scripts\run.ps1
```

Then open:

`http://127.0.0.1:7860`

API health:

`http://127.0.0.1:7860/api/health`

Legacy Gradio studio:

`http://127.0.0.1:7860/legacy`

## API

### Analyze a reference

`POST /api/analyze`

Multipart field:

`file`

### Generate speech

`POST /api/generate`

Multipart fields:

- `text`
- `language`
- `ref_text`
- `file`

The endpoint returns a WAV file when generation succeeds.

## Indian languages

Tamil, Telugu, Malayalam, Hindi, Kannada, Bengali, Gujarati, Marathi, Odia, Punjabi and Assamese.

Only languages actually supported by the installed model should be presented as available.

## Privacy

Reference recordings are not committed to this repository. Keep personal voice samples local. Browser-side voice profiles/history are stored locally in the user's browser.

## Responsible use

Use only voices you own or have explicit permission to clone. Do not use the project for impersonation, fraud, deceptive identity claims, or unauthorized voice cloning.

Official model project: https://github.com/AI4Bharat/IndicF5

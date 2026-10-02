# 🎙️ AudioLab — IndicF5 Voice Cloning

Tamil-first, Indian-language voice cloning studio using AI4Bharat IndicF5.

## V5 pipeline

Reference audio → quality analysis → cleanup → exact transcript → IndicF5 → WAV output

### Supported Indian languages

Tamil, Telugu, Malayalam, Hindi, Kannada, Bengali, Gujarati, Marathi, Odia, Punjabi and Assamese.

## Features

- Reference voice upload / microphone recording
- Reference quality analysis
- Automatic reference cleanup
- Exact reference transcript conditioning
- Text-to-speech voice cloning
- Tamil-first interface
- Modular engine architecture
- Local inference

## Setup

Recommended Python: 3.10.

```powershell
.\scripts\setup_windows.ps1
huggingface-cli login
.\scripts\run.ps1
```

Then open `http://127.0.0.1:7860`.

The IndicF5 weights are downloaded from the official Hugging Face model when first loaded.

Official project: https://github.com/AI4Bharat/IndicF5

## Privacy

Reference recordings are not committed to this repository. Keep personal voice samples local.

## Responsible use

Use only voices you own or have explicit permission to clone. Do not use the project for impersonation, fraud, or misleading identity claims.

# AudioLab — IndicF5 Voice Studio

Local high-quality Indian-language voice cloning studio.

This repository contains the V5 application built around AI4Bharat IndicF5 for reference-guided speech generation. IndicF5 documents support for 11 Indian languages including Tamil, Telugu, Malayalam, Hindi, Kannada, Bengali, Gujarati, Marathi, Odia, Punjabi and Assamese.

## Features
- Reference voice upload/recording
- Reference quality analysis
- Exact reference transcript conditioning
- Tamil-first UI
- Indian-language selection
- Local WAV generation
- Modular engine architecture

## Run on Windows

```powershell
.\scripts\setup_windows.ps1
huggingface-cli login
.\scripts\run.ps1
```

Open `http://127.0.0.1:7860`.

Official IndicF5 project: https://github.com/AI4Bharat/IndicF5

Use only voices you own or have explicit permission to clone.

# Audiolab — $0 Local Voice Generation

This is the zero-cost development path for Audiolab. The browser UI runs locally and calls the FastAPI IndicF5 backend on the same machine. No RunPod, paid Hugging Face hardware, or hosted GPU is required.

## Requirements

- Windows 10/11
- Python 3.11.x recommended
- 8 GB+ RAM recommended
- NVIDIA GPU is optional. If CUDA is available to the installed PyTorch build, the backend uses it automatically; otherwise it falls back to CPU.
- A Hugging Face account with access to `ai4bharat/IndicF5`

## First setup

1. Clone the repository.
2. Open PowerShell in the repository folder.
3. Copy `backend/.env.example` to `backend/.env`.
4. Put your Hugging Face read token in `backend/.env` as `HF_TOKEN=...`. Never commit this file.
5. Run:

```powershell
.\scripts\run-audiolab-local.ps1
```

The launcher creates `backend/.venv`, installs the backend requirements, starts FastAPI on `http://127.0.0.1:8000`, starts the static UI on `http://127.0.0.1:5500`, and opens the UI.

## Manual API check

Open:

`http://127.0.0.1:8000/health`

The response should report `status: ok`, the IndicF5 model, and the supported Indian languages.

## Voice generation

1. Open the local Audiolab UI.
2. Upload or record a reference voice you own or have permission to use.
3. Run reference analysis.
4. Enter the exact transcript of the reference recording.
5. Select Tamil or another supported language.
6. Generate speech.
7. The generated WAV is returned by the local API.

## Why local?

A free static hosting service cannot execute PyTorch/IndicF5 inference. Keeping inference on your own computer is the only dependable zero-cost path for unrestricted development. Hosted GPU providers can be added later without changing the UI/API contract.

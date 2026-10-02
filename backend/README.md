# Audiolab GPU Voice Backend

This service runs the official AI4Bharat IndicF5 inference stack outside Vercel. IndicF5 is reference-guided TTS: generation requires text, reference audio, and the transcript spoken in that reference audio. It supports 11 Indian languages including Tamil, Telugu, Malayalam, Hindi, Kannada, Bengali, Gujarati, Marathi, Odia, Punjabi and Assamese.

## Requirements

- NVIDIA GPU recommended for practical inference
- Python 3.10 when running outside Docker
- Hugging Face access to `ai4bharat/IndicF5`
- A Hugging Face read token exposed as `HF_TOKEN`

The model is gated on Hugging Face, so the account must accept the model conditions before downloading it.

## API

- `GET /health`
- `POST /analyze` with multipart `file`
- `POST /generate` with multipart `text`, `language`, `ref_text`, `file`

## Docker

The included Dockerfile uses a CUDA-enabled PyTorch runtime and installs the official IndicF5 package.

Build:

```bash
docker build -t audiolab-backend ./backend
```

Run with an NVIDIA GPU:

```bash
docker run --gpus all -p 8000:8000 -e HF_TOKEN=YOUR_TOKEN audiolab-backend
```

## GPU cloud deployment

The GitHub Actions workflow builds and publishes:

`ghcr.io/hari-maker-del/audiolab-backend:latest`

A GPU container provider can run that image with:

- GPU enabled
- TCP port `8000`
- `HF_TOKEN` secret configured
- persistent model/cache storage recommended

RunPod is one suitable option for this container architecture. Current published RunPod pricing includes 24 GB+ GPUs and larger 48/80 GB options; pricing changes over time, so check the provider before starting a paid instance.

After the backend receives a public HTTPS URL, configure the Audiolab frontend/API proxy to use that URL.

## Consent

Only use reference recordings you own or have explicit permission to use. This follows the IndicF5 model's terms of use.

# Audiolab GPU Voice Backend

This service runs IndicF5 outside Vercel. Vercel hosts only the lightweight frontend.

## Local GPU

```bash
cd backend
python -m venv .venv
# activate the environment
pip install -r requirements.txt
python server.py
```

API:
- GET `/health`
- POST `/analyze`
- POST `/generate`

## Docker GPU

Build the image:

```bash
docker build -t audiolab-gpu ./backend
```

Run with an NVIDIA GPU:

```bash
docker run --gpus all -p 8000:8000 audiolab-gpu
```

Set the frontend's API base URL to the deployed backend URL.

Only use voice references you own or have permission to use.

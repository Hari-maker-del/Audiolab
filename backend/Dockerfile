FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models/huggingface \
    AUDIOLAB_HOST=0.0.0.0

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg git build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY . .

EXPOSE 8000
CMD ["python", "server.py"]

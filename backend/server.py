from pathlib import Path
import os
import shutil
import tempfile
import threading
import uuid

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from audio import analyze, clean
from audio_tools import (
    trim_audio, normalize_audio, fade_audio, reverse_audio, speed_audio,
    pitch_audio, remove_silence, enhance_voice, merge_audio, mix_audio,
    eq_audio, compress_audio, noise_reduce_audio, reverb_audio, audio_quality,
)
from engine import IndicF5Engine, LANGS

app = FastAPI(title="Audiolab AI Audio Studio API", version="2.2.0")

ALLOWED_ORIGINS = [x.strip() for x in os.getenv(
    "AUDIOLAB_CORS_ORIGINS",
    "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:3000,http://localhost:3000"
).split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"]
)

BASE = Path(__file__).resolve().parent
REF = BASE / "reference"
OUT = BASE / "outputs"
REF.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

engine = None
engine_lock = threading.Lock()

MAX_UPLOAD_BYTES = int(os.getenv("AUDIOLAB_MAX_UPLOAD_MB", "100")) * 1024 * 1024
MAX_TEXT_LENGTH = int(os.getenv("AUDIOLAB_MAX_TEXT_LENGTH", "10000"))


def get_engine():
    global engine
    if engine is None:
        with engine_lock:
            if engine is None:
                engine = IndicF5Engine()
    return engine


def save_upload(upload: UploadFile) -> Path:
    suffix = Path(upload.filename or "audio.wav").suffix or ".wav"
    total = 0
    fd, name = tempfile.mkstemp(prefix="audiolab-upload-", suffix=suffix, dir=OUT)
    path = Path(name)
    try:
        with os.fdopen(fd, "wb") as tmp:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail=f"Audio file exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
                tmp.write(chunk)
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


def make_output(operation: str, suffix: str = ".wav") -> Path:
    return OUT / f"audiolab-{operation}-{uuid.uuid4().hex}{suffix}"


def result_file(path: Path) -> FileResponse:
    return FileResponse(
        path,
        media_type="audio/wav",
        filename=path.name,
        background=BackgroundTask(path.unlink, missing_ok=True),
    )


def validate_text(value: str, field: str):
    value = value or ""
    if not value.strip():
        raise HTTPException(status_code=400, detail=f"{field} is required.")
    if len(value) > MAX_TEXT_LENGTH:
        raise HTTPException(status_code=413, detail=f"{field} exceeds {MAX_TEXT_LENGTH} characters.")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "product": "Audiolab AI Audio Studio",
        "version": "2.2.0",
        "model": "IndicF5",
        "device": get_engine().device if engine is not None else "not_loaded",
        "languages": list(LANGS.keys()),
        "modules": ["timeline", "trim", "normalize", "fade", "reverse", "speed", "pitch", "silence", "enhance", "eq", "compressor", "noise-reduction", "reverb", "merge", "mix", "quality", "voice-generation"],
    }


@app.post("/analyze")
def analyze_endpoint(file: UploadFile = File(...)):
    path = save_upload(file)
    try:
        return analyze(str(path))
    finally:
        path.unlink(missing_ok=True)


@app.post("/quality")
def quality_endpoint(file: UploadFile = File(...)):
    path = save_upload(file)
    try:
        return audio_quality(str(path))
    finally:
        path.unlink(missing_ok=True)


@app.post("/edit/{operation}")
def edit_endpoint(
    operation: str,
    file: UploadFile = File(...),
    start: float = Form(0),
    end: float = Form(0),
    fade_in: float = Form(0),
    fade_out: float = Form(0),
    rate: float = Form(1),
    semitones: float = Form(0),
    strength: float = Form(.65),
    mix: float = Form(.18),
    decay: float = Form(.55),
    threshold_db: float = Form(-18),
    ratio: float = Form(3),
):
    path = save_upload(file)
    output = make_output(operation)
    try:
        try:
            if operation == "trim":
                if start < 0 or end <= start:
                    raise HTTPException(status_code=400, detail="Trim end must be greater than start.")
                trim_audio(str(path), start, end, str(output))
            elif operation == "normalize":
                normalize_audio(str(path), str(output))
            elif operation == "fade":
                if fade_in < 0 or fade_out < 0:
                    raise HTTPException(status_code=400, detail="Fade durations cannot be negative.")
                fade_audio(str(path), str(output), fade_in, fade_out)
            elif operation == "reverse":
                reverse_audio(str(path), str(output))
            elif operation == "speed":
                if rate <= 0:
                    raise HTTPException(status_code=400, detail="Speed must be greater than zero.")
                speed_audio(str(path), str(output), rate)
            elif operation == "pitch":
                pitch_audio(str(path), str(output), semitones)
            elif operation == "silence":
                remove_silence(str(path), str(output))
            elif operation == "enhance":
                enhance_voice(str(path), str(output))
            elif operation == "eq":
                eq_audio(str(path), str(output))
            elif operation == "compress":
                if ratio <= 0:
                    raise HTTPException(status_code=400, detail="Compressor ratio must be greater than zero.")
                compress_audio(str(path), str(output), threshold_db, ratio)
            elif operation == "noise-reduce":
                if not 0 <= strength <= 1:
                    raise HTTPException(status_code=400, detail="Noise reduction strength must be between 0 and 1.")
                noise_reduce_audio(str(path), str(output), strength)
            elif operation == "reverb":
                if not 0 <= mix <= 1 or decay < 0:
                    raise HTTPException(status_code=400, detail="Invalid reverb settings.")
                reverb_audio(str(path), str(output), mix, decay)
            else:
                raise HTTPException(status_code=400, detail="Unsupported operation.")
        except HTTPException:
            raise
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Audio processing failed: {exc}") from exc
        return result_file(output)
    finally:
        path.unlink(missing_ok=True)
        if not output.exists():
            output.unlink(missing_ok=True)


@app.post("/merge")
def merge_endpoint(files: list[UploadFile] = File(...)):
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Upload at least two audio files.")
    paths = [save_upload(f) for f in files]
    output = make_output("merged")
    try:
        merge_audio([str(p) for p in paths], str(output))
        return result_file(output)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Merge failed: {exc}") from exc
    finally:
        for path in paths:
            path.unlink(missing_ok=True)
        if not output.exists():
            output.unlink(missing_ok=True)


@app.post("/mix")
def mix_endpoint(files: list[UploadFile] = File(...), volumes: str = Form("")):
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one audio file.")
    paths = [save_upload(f) for f in files]
    output = make_output("mix")
    try:
        try:
            values = [float(x) for x in volumes.split(",") if x.strip()] if volumes.strip() else None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Volumes must be comma-separated numbers.") from exc
        mix_audio([str(p) for p in paths], str(output), values)
        return result_file(output)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Mix failed: {exc}") from exc
    finally:
        for path in paths:
            path.unlink(missing_ok=True)
        if not output.exists():
            output.unlink(missing_ok=True)


@app.post("/generate")
def generate_endpoint(
    text: str = Form(...),
    language: str = Form("Tamil"),
    ref_text: str = Form(...),
    file: UploadFile = File(...),
):
    validate_text(text, "Text")
    validate_text(ref_text, "Reference transcript")
    if language not in LANGS:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")

    source = save_upload(file)
    cleaned = REF / f"request-reference-{uuid.uuid4().hex}.wav"
    output = make_output("generated")
    try:
        try:
            clean(str(source), cleaned)
            result = get_engine().generate(text, cleaned, ref_text, output)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Voice generation failed: {exc}") from exc
        return result_file(Path(result))
    finally:
        source.unlink(missing_ok=True)
        cleaned.unlink(missing_ok=True)
        if not output.exists():
            output.unlink(missing_ok=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=os.getenv("AUDIOLAB_HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )

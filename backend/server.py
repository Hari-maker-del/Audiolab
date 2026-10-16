from pathlib import Path
import os
import shutil
import tempfile
import threading
import time
import uuid

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from audio import analyze, clean
from audio_generation import EFFECTS, MUSIC_STYLES, generate_sound_effect, generate_music_sketch
from audio_tools import (
    trim_audio, normalize_audio, fade_audio, reverse_audio, speed_audio,
    pitch_audio, remove_silence, enhance_voice, merge_audio, mix_audio,
    eq_audio, compress_audio, noise_reduce_audio, reverb_audio, audio_quality,
)
from engine import IndicF5Engine, LANGS
from speech_to_text import SpeechToTextUnavailable, status as speech_to_text_status, transcribe as transcribe_speech
from voice_conversion import (
    VoiceConversionUnavailable,
    convert_voice,
    get_voice_conversion_status,
)

app = FastAPI(
    title="Audiolab AI Audio Studio API",
    version="2.3.0",
    description=(
        "Local-first audio processing API. Model-backed endpoints require their optional local "
        "dependencies and model weights. Sound effects and music sketches are procedural DSP, "
        "not generative-AI music."
    ),
    contact={"name": "Audiolab", "url": "https://github.com/Hari-maker-del/Audiolab"},
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

ALLOWED_ORIGINS = [x.strip() for x in os.getenv(
    "AUDIOLAB_CORS_ORIGINS",
    "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:3000,http://localhost:3000"
).split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Audiolab-Source-Language", "X-Audiolab-Source-Transcript", "X-Audiolab-Dubbing-Mode"]
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


@app.on_event("startup")
def clean_stale_artifacts():
    """Remove stale request/output artifacts left behind by an abrupt prior shutdown."""
    cutoff = time.time() - 24 * 60 * 60
    prefixes = ("audiolab-upload-", "audiolab-", "request-reference-", "dub-reference-")
    for folder in (OUT, REF):
        try:
            for path in folder.iterdir():
                if not path.is_file() or not path.name.startswith(prefixes):
                    continue
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink(missing_ok=True)
                except OSError:
                    continue
        except OSError:
            continue


def get_engine():
    global engine
    if engine is None:
        with engine_lock:
            if engine is None:
                engine = IndicF5Engine()
    return engine


def save_upload(upload: UploadFile) -> Path:
    # Never trust a client filename as a filesystem suffix.
    supplied_suffix = Path(upload.filename or "audio.wav").suffix.lower()
    allowed_suffixes = {".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".flac", ".aac", ".webm", ".opus"}
    suffix = supplied_suffix if supplied_suffix in allowed_suffixes else ".audio"
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
        "version": "2.3.0",
        "limits": {
            "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
            "max_text_characters": MAX_TEXT_LENGTH,
            "max_concurrent_model_loads": 1,
        },
        "api_docs": "/docs",
        "model": "IndicF5",
        "device": engine.device if engine is not None else "not_loaded",
        "inference": {
            "state": "loaded" if engine is not None else "not_loaded",
            "loaded": engine is not None,
            "model_id": "ai4bharat/IndicF5",
            "note": "The model loads on the first generation request. A healthy API does not mean the model weights have already loaded."
        },
        "languages": list(LANGS.keys()),
        "voice_conversion": get_voice_conversion_status(),
        "speech_to_text": speech_to_text_status(),
        "modules": ["timeline", "trim", "normalize", "fade", "reverse", "speed", "pitch", "silence", "enhance", "eq", "compressor", "noise-reduction", "reverb", "merge", "mix", "quality", "voice-generation", "voice-conversion", "speech-to-text", "sound-effects", "music-sketch", "dubbing-assist"],
    }


@app.get("/languages")
def languages_endpoint():
    """Expose the actual language allow-list and explain model conditioning."""
    return {
        "model": "ai4bharat/IndicF5",
        "languages": [
            {"name": name, "code": code, "text_conditioning": "IndicF5 derives pronunciation from the supplied text/reference; the current wrapper does not expose a separate language-token argument."}
            for name, code in LANGS.items()
        ],
        "note": "Choose the language matching the script and spoken content. Tanglish/Latin-script input may behave differently from native-script text; always listen to the result.",
    }


@app.get("/models")
def models_endpoint():
    """Report real local model state without triggering heavy lazy loading."""
    return {
        "models": [
            {
                "id": "indicf5",
                "name": "AI4Bharat IndicF5",
                "task": "text-to-speech",
                "state": "loaded" if engine is not None else "not_loaded",
                "available": engine is not None,
                "device": engine.device if engine is not None else "not_loaded",
                "note": "IndicF5 loads on the first generation request; model access and dependencies may be required.",
            },
            get_voice_conversion_status(),
            speech_to_text_status(),
        ]
    }


@app.post("/transcribe")
def transcribe_endpoint(file: UploadFile = File(...), language: str = Form("")):
    """Transcribe an uploaded recording with the optional local Whisper model."""
    path = save_upload(file)
    try:
        try:
            return transcribe_speech(path, language or None)
        except SpeechToTextUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Speech transcription failed: {exc}") from exc
    finally:
        path.unlink(missing_ok=True)


@app.post("/sound-effects")
def sound_effect_endpoint(effect: str = Form(...), duration: float = Form(3.0), seed: int = Form(7)):
    """Generate a deterministic local sound effect WAV using DSP."""
    output = make_output("sfx")
    try:
        generate_sound_effect(effect.strip().lower(), duration, output, seed)
        return result_file(output)
    except ValueError as exc:
        output.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        output.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Sound-effect generation failed: {exc}") from exc


@app.post("/music-sketch")
def music_sketch_endpoint(style: str = Form(...), duration: float = Form(12.0), seed: int = Form(11)):
    """Generate a local procedural music bed; this is not an AI music model."""
    output = make_output("music-sketch")
    try:
        generate_music_sketch(style.strip().lower(), duration, output, seed)
        return result_file(output)
    except ValueError as exc:
        output.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        output.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Music sketch generation failed: {exc}") from exc


@app.post("/dub")
def dubbing_assist_endpoint(
    source_file: UploadFile = File(...),
    target_file: UploadFile = File(...),
    source_language: str = Form(""),
    target_language: str = Form(...),
    translated_text: str = Form(...),
    ref_text: str = Form(...),
    consent: bool = Form(...),
):
    """Create a target-language dubbed voice track using a user-reviewed translation."""
    if not consent:
        raise HTTPException(status_code=400, detail="Confirm you have rights to use both recordings and the target voice.")
    validate_text(translated_text, "Translated script")
    validate_text(ref_text, "Target voice reference transcript")
    if target_language not in LANGS:
        raise HTTPException(status_code=400, detail=f"Unsupported target language: {target_language}")
    source = target = None
    output = make_output("dubbed")
    response_ready = False
    try:
        source = save_upload(source_file)
        target = save_upload(target_file)
        try:
            source_result = transcribe_speech(source, source_language or None)
            cleaned = REF / f"dub-reference-{uuid.uuid4().hex}.wav"
            clean(str(target), cleaned)
            try:
                get_engine().generate(translated_text, cleaned, ref_text, output)
            finally:
                cleaned.unlink(missing_ok=True)
        except SpeechToTextUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Dubbing assist failed: {exc}") from exc
        import base64
        response = FileResponse(
            output, media_type="audio/wav", filename=output.name,
            headers={
                "X-Audiolab-Source-Language": str(source_result.get("language") or "unknown"),
                "X-Audiolab-Source-Transcript": base64.urlsafe_b64encode(source_result.get("text", "").encode("utf-8")[:1200]).decode("ascii"),
                "X-Audiolab-Dubbing-Mode": "user-reviewed-translation",
            },
            background=BackgroundTask(output.unlink, missing_ok=True),
        )
        response_ready = True
        return response
    finally:
        if source is not None:
            source.unlink(missing_ok=True)
        if target is not None:
            target.unlink(missing_ok=True)
        if not response_ready:
            output.unlink(missing_ok=True)


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
    paths = []
    output = make_output("merged")
    try:
        for upload in files:
            paths.append(save_upload(upload))
        merge_audio([str(p) for p in paths], str(output))
        return result_file(output)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Merge failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Merge failed due to an internal processing error.") from exc
    finally:
        for path in paths:
            path.unlink(missing_ok=True)
        if not output.exists():
            output.unlink(missing_ok=True)


@app.post("/mix")
def mix_endpoint(files: list[UploadFile] = File(...), volumes: str = Form("")):
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one audio file.")
    paths = []
    output = make_output("mix")
    try:
        for upload in files:
            paths.append(save_upload(upload))
        try:
            values = [float(x) for x in volumes.split(",") if x.strip()] if volumes.strip() else None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Volumes must be comma-separated numbers.") from exc
        mix_audio([str(p) for p in paths], str(output), values)
        return result_file(output)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Mix failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Mix failed due to an internal processing error.") from exc
    finally:
        for path in paths:
            path.unlink(missing_ok=True)
        if not output.exists():
            output.unlink(missing_ok=True)


@app.post("/voice-convert")
def voice_convert_endpoint(
    source_file: UploadFile = File(...),
    target_file: UploadFile = File(...),
    consent: bool = Form(...),
):
    """Convert an existing source performance toward a target reference voice."""
    if not consent:
        raise HTTPException(
            status_code=400,
            detail="Confirm that you own the source recording and have permission to use the target voice.",
        )

    source = None
    target = None
    output = make_output("voice-converted")
    response_ready = False
    try:
        source = save_upload(source_file)
        target = save_upload(target_file)
        try:
            result_path = convert_voice(str(source), str(target), str(output))
        except VoiceConversionUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Voice conversion failed: {exc}") from exc

        response = result_file(Path(result_path))
        response_ready = True
        return response
    finally:
        if source is not None:
            source.unlink(missing_ok=True)
        if target is not None:
            target.unlink(missing_ok=True)
        if not response_ready:
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
    response_ready = False
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
        response = result_file(Path(result))
        response_ready = True
        return response
    finally:
        source.unlink(missing_ok=True)
        cleaned.unlink(missing_ok=True)
        if not response_ready:
            output.unlink(missing_ok=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=os.getenv("AUDIOLAB_HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
    )

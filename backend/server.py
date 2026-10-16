from pathlib import Path
import os
import json
import shutil
import tempfile
import threading
import time
import uuid
import zipfile

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from audio import analyze, clean
from voice_agent import understand_intent, create_reply
from dubbing import build_srt, validate_dub_segments
from audio_generation import EFFECTS, MUSIC_STYLES, generate_sound_effect, generate_music_sketch
from ai_music import (
    MusicGenerationFailed, MusicGenerationUnavailable, generate_ai_music,
    music_generation_status,
)
from audio_tools import (
    trim_audio, normalize_audio, fade_audio, reverse_audio, speed_audio,
    pitch_audio, remove_silence, enhance_voice, merge_audio, mix_audio,
    eq_audio, compress_audio, noise_reduce_audio, reverb_audio, audio_quality,
)
from engine import IndicF5Engine, LANGS
from speech_to_text import SpeechToTextUnavailable, status as speech_to_text_status, transcribe as transcribe_speech
from source_separation import (
    SeparationFailed, SeparationUnavailable, separate_to_stems, separation_status,
)
from voice_conversion import (
    VoiceConversionUnavailable,
    convert_voice,
    get_voice_conversion_status,
)

app = FastAPI(
    title="Audiolab AI Audio Studio API",
    version="2.7.0",
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
        "version": "2.7.0",
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
        "source_separation": separation_status(),
        "ai_music": music_generation_status(),
        "voice_agent": {"state": "ready", "mode": "local-rule-based-intent", "speech_input": speech_to_text_status()["available"], "spoken_output": "IndicF5 reference voice required"},
        "modules": ["timeline", "trim", "normalize", "fade", "reverse", "speed", "pitch", "silence", "enhance", "eq", "compressor", "noise-reduction", "reverb", "merge", "mix", "quality", "voice-generation", "voice-conversion", "speech-to-text", "sound-effects", "music-sketch", "dubbing-assist", "timed-dubbing", "subtitle-export", "vocal-isolation", "ai-music-generation", "voice-agent"],
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
            separation_status(),
            music_generation_status(),
            {"id": "voice-agent", "name": "Audiolab Voice Agent", "task": "conversational-assistant", "state": "ready", "mode": "local-rule-based-intent"},
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


@app.post("/voice-agent")
def voice_agent_endpoint(
    message: str = Form(""),
    audio_file: UploadFile | None = File(None),
    language: str = Form(""),
    voice_reference: UploadFile | None = File(None),
    voice_reference_text: str = Form(""),
    consent: bool = Form(False),
):
    """Understand a typed/spoken request and optionally speak the answer with IndicF5."""
    typed_message = (message or "").strip()
    if not typed_message and audio_file is None:
        raise HTTPException(status_code=400, detail="Enter a message or upload a speech recording.")
    if voice_reference is not None:
        if not consent:
            raise HTTPException(status_code=400, detail="Confirm you have permission to use the reply voice reference.")
        validate_text(voice_reference_text, "Exact voice-reference transcript")

    input_path = reference_path = cleaned_reference = output = None
    try:
        if audio_file is not None:
            input_path = save_upload(audio_file)
            try:
                transcription = transcribe_speech(input_path, language or None)
            except SpeechToTextUnavailable as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            typed_message = str(transcription.get("text") or "").strip()
            if not typed_message:
                raise HTTPException(status_code=400, detail="No speech was recognized. Try a clearer or shorter recording.")

        try:
            intent_result = understand_intent(typed_message)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        reply = create_reply(intent_result)
        reply["recognized_text"] = typed_message
        reply["transcription_language"] = language or "auto"
        reply["conversation_memory"] = "client-managed; no server-side conversation history stored"

        if voice_reference is None:
            return reply

        reference_path = save_upload(voice_reference)
        cleaned_reference = REF / f"agent-reference-{uuid.uuid4().hex}.wav"
        clean(str(reference_path), cleaned_reference)
        output = make_output("voice-agent-reply")
        try:
            get_engine().generate(reply["reply"], cleaned_reference, voice_reference_text, output)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Spoken reply generation failed. Check IndicF5 setup and reference audio.") from exc

        import base64
        response = FileResponse(
            output,
            media_type="audio/wav",
            filename="audiolab-voice-agent-reply.wav",
            headers={
                "X-Audiolab-Agent-Intent": reply["intent"],
                "X-Audiolab-Agent-Reply": base64.urlsafe_b64encode(reply["reply"].encode("utf-8")).decode("ascii"),
                "X-Audiolab-Agent-Recognized": base64.urlsafe_b64encode(typed_message.encode("utf-8")[:1600]).decode("ascii"),
            },
            background=BackgroundTask(output.unlink, missing_ok=True),
        )
        output = None
        return response
    finally:
        for path in (input_path, reference_path, cleaned_reference, output):
            if path is not None:
                path.unlink(missing_ok=True)


@app.post("/music-generate")
def ai_music_endpoint(prompt: str = Form(...), duration: float = Form(8.0)):
    """Generate music from a text prompt using the optional local MusicGen model."""
    output = make_output("ai-music")
    try:
        generate_ai_music(prompt, duration, output)
        return result_file(output)
    except MusicGenerationUnavailable as exc:
        output.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        output.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MusicGenerationFailed as exc:
        output.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        output.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="AI music generation failed due to an internal processing error.") from exc


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


def cleanup_dub_project(archive_path: Path, work_dir: Path):
    archive_path.unlink(missing_ok=True)
    shutil.rmtree(work_dir, ignore_errors=True)


@app.post("/dub-transcribe")
def dub_transcribe_endpoint(
    source_file: UploadFile = File(...),
    source_language: str = Form(""),
):
    """Return editable source speech segments with timestamps for a dubbing timeline."""
    source = save_upload(source_file)
    try:
        try:
            result = transcribe_speech(source, source_language or None)
        except SpeechToTextUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        segments = result.get("segments") or []
        if not segments:
            raise HTTPException(status_code=422, detail="No timestamped speech segments were returned.")
        if len(segments) > 120:
            raise HTTPException(status_code=413, detail="This recording produced more than 120 segments. Use a shorter clip.")
        return {
            "language": result.get("language") or "unknown",
            "duration": result.get("duration", 0),
            "text": result.get("text", ""),
            "segments": [
                {
                    "start": round(float(row["start"]), 3),
                    "end": round(float(row["end"]), 3),
                    "source_text": str(row.get("text") or ""),
                    "translated_text": "",
                }
                for row in segments
            ],
            "provider": "local faster-whisper",
            "note": "Review every transcription and enter the translated text. Translation is not automatic.",
        }
    finally:
        source.unlink(missing_ok=True)


@app.post("/dub-render")
def dub_render_endpoint(
    target_file: UploadFile = File(...),
    segments_json: str = Form(...),
    target_language: str = Form(...),
    ref_text: str = Form(...),
    consent: bool = Form(False),
):
    """Generate a sentence-timed dubbed voice track plus SRT in a downloadable ZIP."""
    if not consent:
        raise HTTPException(status_code=400, detail="Confirm you have permission to use the target voice reference.")
    validate_text(ref_text, "Target voice reference transcript")
    if target_language not in LANGS:
        raise HTTPException(status_code=400, detail=f"Unsupported target language: {target_language}")
    try:
        parsed = json.loads(segments_json)
        segments = validate_dub_segments(parsed)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    import librosa
    import numpy as np
    import soundfile as sf

    work_dir = OUT / f"audiolab-dub-project-{uuid.uuid4().hex}"
    archive_path = make_output("dub-project", ".zip")
    target = cleaned_reference = None
    response_ready = False
    try:
        work_dir.mkdir(parents=True, exist_ok=False)
        target = save_upload(target_file)
        cleaned_reference = REF / f"dub-project-reference-{uuid.uuid4().hex}.wav"
        clean(str(target), cleaned_reference)

        sample_rate = 24000
        duration = max(row["end"] for row in segments)
        timeline = np.zeros(int(np.ceil(duration * sample_rate)) + 1, dtype=np.float32)
        fit_report = []
        active_engine = get_engine()

        for row in segments:
            segment_path = work_dir / f"segment-{row['index']:03d}.wav"
            try:
                active_engine.generate(
                    row["translated_text"], cleaned_reference, ref_text, segment_path
                )
                speech, rate = sf.read(str(segment_path), dtype="float32", always_2d=False)
                if getattr(speech, "ndim", 1) > 1:
                    speech = np.mean(speech, axis=1)
                speech = np.asarray(speech, dtype=np.float32)
                if not speech.size or not np.isfinite(speech).all():
                    raise ValueError(f"Generated audio for segment {row['index']} was empty or invalid.")
                if int(rate) != sample_rate:
                    speech = librosa.resample(speech, orig_sr=int(rate), target_sr=sample_rate)
                slot_samples = max(1, int(round((row["end"] - row["start"]) * sample_rate)))
                fit = "natural"
                if len(speech) > slot_samples:
                    rate_ratio = len(speech) / slot_samples
                    if rate_ratio <= 2.0:
                        speech = librosa.effects.time_stretch(speech, rate=rate_ratio)
                        fit = "time-stretched"
                    if len(speech) > slot_samples:
                        speech = speech[:slot_samples]
                        fit = "trimmed-to-slot"
                start_sample = int(round(row["start"] * sample_rate))
                end_sample = min(start_sample + len(speech), len(timeline))
                if end_sample > start_sample:
                    timeline[start_sample:end_sample] += speech[:end_sample - start_sample]
                fit_report.append({
                    "index": row["index"],
                    "start": row["start"],
                    "end": row["end"],
                    "fit": fit,
                    "slot_seconds": round(slot_samples / sample_rate, 3),
                })
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"Segment {row['index']}: {exc}") from exc
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Speech generation failed for segment {row['index']}. Check local IndicF5 setup and reference audio.") from exc
            finally:
                segment_path.unlink(missing_ok=True)

        peak = float(np.max(np.abs(timeline))) if timeline.size else 0.0
        if peak > 0.98:
            timeline *= (0.98 / peak)
        dubbed_path = work_dir / "dubbed_voice.wav"
        sf.write(str(dubbed_path), timeline, sample_rate)
        subtitle_path = work_dir / "subtitles.srt"
        subtitle_path.write_text(build_srt(segments), encoding="utf-8")
        metadata_path = work_dir / "segments.json"
        metadata_path.write_text(json.dumps({
            "target_language": target_language,
            "sample_rate": sample_rate,
            "alignment": "source speech timestamps; generated segments are time-stretched or trimmed when longer than their slots",
            "segments": segments,
            "fit_report": fit_report,
            "background_audio_included": False,
            "lip_sync": False,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(dubbed_path, arcname="dubbed_voice.wav")
            bundle.write(subtitle_path, arcname="subtitles.srt")
            bundle.write(metadata_path, arcname="segments.json")
        response = FileResponse(
            archive_path,
            media_type="application/zip",
            filename="audiolab-dubbing-project.zip",
            background=BackgroundTask(cleanup_dub_project, archive_path, work_dir),
        )
        response_ready = True
        return response
    finally:
        if target is not None:
            target.unlink(missing_ok=True)
        if cleaned_reference is not None:
            cleaned_reference.unlink(missing_ok=True)
        if not response_ready:
            archive_path.unlink(missing_ok=True)
            shutil.rmtree(work_dir, ignore_errors=True)


def cleanup_separation_artifacts(archive_path: Path, work_dir: Path):
    """Clean the archive and its model output files after the response is sent."""
    archive_path.unlink(missing_ok=True)
    shutil.rmtree(work_dir, ignore_errors=True)


@app.post("/separate")
def separate_endpoint(file: UploadFile = File(...)):
    """Separate an uploaded track into vocals and instrumental WAVs using local Demucs."""
    source = None
    work_dir = OUT / f"audiolab-separation-{uuid.uuid4().hex}"
    archive_path = make_output("separated-stems", ".zip")
    response_ready = False
    try:
        source = save_upload(file)
        work_dir.mkdir(parents=True, exist_ok=True)
        try:
            vocals, instrumental = separate_to_stems(source, work_dir)
        except SeparationUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except SeparationFailed as exc:
            message = str(exc)
            status_code = 504 if "exceeded the" in message.lower() else 500
            raise HTTPException(status_code=status_code, detail=message) from exc

        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(vocals, arcname="vocals.wav")
            bundle.write(instrumental, arcname="instrumental.wav")

        response = FileResponse(
            archive_path,
            media_type="application/zip",
            filename="audiolab-separated-stems.zip",
            background=BackgroundTask(cleanup_separation_artifacts, archive_path, work_dir),
        )
        response_ready = True
        return response
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Source separation failed due to an internal processing error.") from exc
    finally:
        if source is not None:
            source.unlink(missing_ok=True)
        if not response_ready:
            archive_path.unlink(missing_ok=True)
            shutil.rmtree(work_dir, ignore_errors=True)


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

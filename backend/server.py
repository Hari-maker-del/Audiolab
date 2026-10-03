from pathlib import Path
import shutil
import tempfile

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from audio import analyze, clean
from engine import IndicF5Engine, LANGS

app = FastAPI(title="Audiolab GPU Voice API", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE = Path(__file__).resolve().parent
REF = BASE / "reference"
OUT = BASE / "outputs"
REF.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

engine = None


def get_engine():
    global engine
    if engine is None:
        engine = IndicF5Engine()
    return engine


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": "IndicF5",
        "device": get_engine().device if engine is not None else "not_loaded",
        "languages": list(LANGS.keys()),
    }


@app.post("/analyze")
async def analyze_endpoint(file: UploadFile = File(...)):
    suffix = Path(file.filename or "reference.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        path = Path(tmp.name)

    try:
        return analyze(str(path))
    finally:
        path.unlink(missing_ok=True)


@app.post("/generate")
async def generate_endpoint(
    text: str = Form(...),
    language: str = Form("Tamil"),
    ref_text: str = Form(...),
    file: UploadFile = File(...),
):
    if not text.strip():
        return {"error": "Text is required."}
    if not ref_text.strip():
        return {"error": "Exact reference transcript is required."}
    if language not in LANGS:
        return {"error": f"Unsupported language: {language}"}

    suffix = Path(file.filename or "reference.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        source = Path(tmp.name)

    cleaned = REF / "request_reference.wav"
    output = OUT / "audiolab_generated.wav"

    try:
        clean(str(source), cleaned)
        result = get_engine().generate(text, cleaned, ref_text, output)
        return FileResponse(
            result,
            media_type="audio/wav",
            filename="audiolab_generated.wav",
        )
    finally:
        source.unlink(missing_ok=True)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )

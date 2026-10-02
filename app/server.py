from pathlib import Path
import shutil
import tempfile

import gradio as gr
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from audio import analyze, clean
from engine import IndicF5Engine, LANGS

BASE = Path(__file__).resolve().parents[1]
REF = BASE / "reference"
OUT = BASE / "outputs"
FRONTEND = BASE / "frontend"
REF.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

engine = None


def get_engine():
    global engine
    if engine is None:
        engine = IndicF5Engine()
    return engine


def inspect_reference(path):
    if not path:
        raise gr.Error("Upload your reference voice.")
    x = analyze(path)
    return (
        f"Duration: {x['duration']} sec\n"
        f"RMS: {x['rms']}\n"
        f"Silence ratio: {x['silence']}\n"
        f"Reference quality: {x['score']}/100"
    )


def generate(text, language, ref_audio, ref_text):
    if not text.strip():
        raise gr.Error("Enter text.")
    if not ref_audio:
        raise gr.Error("Upload a reference voice.")
    if not ref_text.strip():
        raise gr.Error("Enter the exact transcript of the reference recording.")
    cleaned = REF / "clean_reference.wav"
    clean(ref_audio, cleaned)
    output = OUT / "indicf5_cloned.wav"
    try:
        return get_engine().generate(text, cleaned, ref_text, output)
    except Exception as e:
        raise gr.Error(str(e))


with gr.Blocks(title="Audiolab Legacy Studio") as demo:
    gr.Markdown("# Audiolab — IndicF5 Studio")
    gr.Markdown("Local Indian-language voice generation. Use only voices you own or have permission to clone.")
    with gr.Row():
        with gr.Column():
            ref_audio = gr.Audio(label="Reference Voice", type="filepath", sources=["upload", "microphone"])
            inspect_btn = gr.Button("Analyze Voice")
            analysis = gr.Textbox(label="Reference Quality", lines=5)
            inspect_btn.click(inspect_reference, ref_audio, analysis)
            ref_text = gr.Textbox(label="Exact Reference Transcript", lines=5)
        with gr.Column():
            language = gr.Dropdown(list(LANGS.keys()), value="Tamil", label="Target Language")
            text = gr.Textbox(label="Text to Speak", lines=10, placeholder="தமிழில் பேச வேண்டிய உரையை இங்கே உள்ளிடுங்கள்...")
            generate_btn = gr.Button("Clone Voice", variant="primary")
            result = gr.Audio(label="Cloned Voice", type="filepath")
    generate_btn.click(generate, inputs=[text, language, ref_audio, ref_text], outputs=result)

app = FastAPI(title="Audiolab API", version="5.1.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "model": "IndicF5", "languages": list(LANGS.keys())}


@app.post("/api/analyze")
async def api_analyze(file: UploadFile = File(...)):
    suffix = Path(file.filename or "reference.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        temp_path = Path(tmp.name)
    try:
        return analyze(str(temp_path))
    finally:
        temp_path.unlink(missing_ok=True)


@app.post("/api/generate")
async def api_generate(
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
        source_path = Path(tmp.name)

    cleaned = REF / "web_reference.wav"
    output = OUT / "audiolab_generated.wav"
    try:
        clean(str(source_path), cleaned)
        result = get_engine().generate(text, cleaned, ref_text, output)
        return FileResponse(result, media_type="audio/wav", filename="audiolab_generated.wav")
    finally:
        source_path.unlink(missing_ok=True)


# Keep the original Gradio studio available under /legacy.
app = gr.mount_gradio_app(app, demo, path="/legacy")

# Serve the Stitch frontend after API and legacy routes so they remain reachable.
if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=7860)

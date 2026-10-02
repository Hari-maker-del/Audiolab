from pathlib import Path
import gradio as gr

from audio import analyze, clean
from engine import IndicF5Engine, LANGS

BASE = Path(__file__).resolve().parents[1]
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


with gr.Blocks(title="AudioLab — IndicF5 Voice Studio") as demo:
    gr.Markdown("# 🇮🇳 AudioLab — IndicF5 Voice Studio")
    gr.Markdown("High-quality local Indian-language voice cloning. Use only a voice you own or have permission to clone.")

    with gr.Row():
        with gr.Column():
            ref_audio = gr.Audio(label="Reference Voice", type="filepath", sources=["upload", "microphone"])
            inspect_btn = gr.Button("🔎 Analyze Voice")
            analysis = gr.Textbox(label="Reference Quality", lines=5)
            inspect_btn.click(inspect_reference, ref_audio, analysis)
            ref_text = gr.Textbox(label="Exact Reference Transcript", lines=5)

        with gr.Column():
            language = gr.Dropdown(list(LANGS.keys()), value="Tamil", label="Target Language")
            text = gr.Textbox(label="Text to Speak", lines=10, placeholder="தமிழில் பேச வேண்டிய உரையை இங்கே எழுதுங்கள்...")
            generate_btn = gr.Button("🚀 Clone Voice", variant="primary")
            result = gr.Audio(label="Cloned Voice", type="filepath")

    generate_btn.click(generate, inputs=[text, language, ref_audio, ref_text], outputs=result)

    gr.Markdown("Accurate reference transcription and clean single-speaker audio improve cloning consistency.")

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)

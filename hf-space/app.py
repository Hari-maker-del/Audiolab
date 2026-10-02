import os
import tempfile
from pathlib import Path

import gradio as gr
import numpy as np
import soundfile as sf
import spaces
import torch
from transformers import AutoModel

MODEL_ID = "ai4bharat/IndicF5"
LANGUAGES = [
    "Tamil", "Telugu", "Malayalam", "Hindi", "Kannada", "Bengali",
    "Gujarati", "Marathi", "Odia", "Punjabi", "Assamese"
]

# IndicF5 is loaded once at Space startup. ZeroGPU provides CUDA emulation
# outside the decorated function and attaches real GPU compute during calls.
model = AutoModel.from_pretrained(
    MODEL_ID,
    trust_remote_code=True,
    token=os.getenv("HF_TOKEN") or None,
)
model = model.to("cuda")


def _normalize_audio(audio):
    if audio is None:
        raise ValueError("No audio was generated.")
    if getattr(audio, "dtype", None) == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    else:
        audio = np.asarray(audio, dtype=np.float32)
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak > 1.0:
            audio = audio / peak
    return np.clip(audio, -1.0, 1.0)


def analyze_reference(ref_audio):
    if not ref_audio:
        return "No reference audio", ""
    try:
        data, sr = sf.read(ref_audio, always_2d=False)
        data = np.asarray(data, dtype=np.float32)
        if data.ndim > 1:
            data = data.mean(axis=1)
        duration = len(data) / max(sr, 1)
        rms = float(np.sqrt(np.mean(np.square(data)))) if len(data) else 0.0
        silence = float(np.mean(np.abs(data) < 0.01)) if len(data) else 1.0
        if duration < 2:
            quality = "Too short"
        elif duration > 15:
            quality = "Trim to ≤15s"
        elif silence > 0.55:
            quality = "Too much silence"
        elif rms < 0.01:
            quality = "Too quiet"
        else:
            quality = "Good reference"
        return (
            f"Duration: {duration:.1f}s · RMS: {rms:.4f} · Silence: {silence * 100:.0f}%",
            quality,
        )
    except Exception as exc:
        return f"Analysis error: {exc}", "Check audio format"


@spaces.GPU(duration=120)
def generate_voice(text, ref_audio, ref_text, language):
    if not text or not text.strip():
        raise gr.Error("Generation text is required.")
    if not ref_audio:
        raise gr.Error("Reference audio is required.")
    if not ref_text or not ref_text.strip():
        raise gr.Error("The exact reference transcript is required.")
    if language not in LANGUAGES:
        raise gr.Error("Unsupported language.")

    # IndicF5 itself performs the voice/prosody conditioning. Do not alter
    # the reference audio before inference because that can reduce similarity.
    audio = model(
        text.strip(),
        ref_audio_path=ref_audio,
        ref_text=ref_text.strip(),
    )
    audio = _normalize_audio(audio)

    output = Path(tempfile.mkstemp(prefix="audiolab_", suffix=".wav")[1])
    sf.write(output, audio, samplerate=24000, subtype="PCM_16")
    return str(output)


with gr.Blocks(title="Audiolab — IndicF5") as demo:
    gr.Markdown(
        """
        # 🎙️ Audiolab
        ### High-fidelity Indian-language voice generation

        Use only a voice recording that you own or have explicit permission to use.
        For the strongest speaker similarity, use a clean single-speaker reference
        shorter than about 15 seconds and provide its exact transcript.
        """
    )

    with gr.Row():
        with gr.Column():
            text = gr.Textbox(
                label="Text to generate",
                placeholder="உங்கள் உரையை இங்கே உள்ளிடுங்கள்...",
                lines=5,
            )
            language = gr.Dropdown(
                choices=LANGUAGES,
                value="Tamil",
                label="Language",
            )
            ref_audio = gr.Audio(
                sources=["upload", "microphone"],
                type="filepath",
                format="wav",
                label="Reference voice",
            )
            ref_text = gr.Textbox(
                label="Exact reference transcript",
                placeholder="Type exactly what is spoken in the reference recording.",
                lines=4,
            )
            with gr.Row():
                analyze = gr.Button("Analyze reference")
                generate = gr.Button("Generate voice", variant="primary")

        with gr.Column():
            analysis = gr.Textbox(label="Reference analysis", interactive=False)
            quality = gr.Textbox(label="Quality check", interactive=False)
            output = gr.Audio(label="Generated speech", type="filepath", format="wav")

    analyze.click(analyze_reference, inputs=ref_audio, outputs=[analysis, quality], api_name="analyze")
    generate.click(generate_voice, inputs=[text, ref_audio, ref_text, language], outputs=output, api_name="generate")

    gr.Markdown(
        "IndicF5 supports Assamese, Bengali, Gujarati, Hindi, Kannada, Malayalam, "
        "Marathi, Odia, Punjabi, Tamil and Telugu."
    )

if __name__ == "__main__":
    demo.queue(default_concurrency_limit=1).launch()

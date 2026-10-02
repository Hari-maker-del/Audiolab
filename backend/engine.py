import os

import numpy as np
import soundfile as sf
import torch
from transformers import AutoModel

MODEL_ID = "ai4bharat/IndicF5"
LANGS = {
    "Tamil": "ta", "Telugu": "te", "Malayalam": "ml", "Hindi": "hi",
    "Kannada": "kn", "Bengali": "bn", "Gujarati": "gu", "Marathi": "mr",
    "Odia": "or", "Punjabi": "pa", "Assamese": "as",
}


class IndicF5Engine:
    def __init__(self):
        token = os.getenv("HF_TOKEN") or None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = AutoModel.from_pretrained(
            MODEL_ID,
            trust_remote_code=True,
            token=token,
        ).to(self.device)
        self.model.eval()

    def generate(self, text, ref_audio, ref_text, output):
        if not text.strip():
            raise ValueError("Text is required.")
        if not ref_text.strip():
            raise ValueError("Exact reference transcript is required.")

        audio = self.model(
            text,
            ref_audio_path=str(ref_audio),
            ref_text=ref_text,
        )

        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0

        sf.write(
            str(output),
            np.asarray(audio, dtype=np.float32),
            samplerate=24000,
        )
        return str(output)

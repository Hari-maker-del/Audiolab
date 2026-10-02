import { Client, handle_file } from "https://cdn.jsdelivr.net/npm/@gradio/client/dist/index.min.js";

const SPACE = "Hari-maker-del/audiolab-zerogpu";
const LOCAL_API = "http://127.0.0.1:8000";
const IS_LOCAL = ["localhost", "127.0.0.1"].includes(window.location.hostname);

let clientPromise;

async function getHFClient() {
  if (!clientPromise) {
    clientPromise = Client.connect(SPACE, {
      status_callback: (status) => {
        window.dispatchEvent(new CustomEvent("audiolab-hf-status", { detail: status }));
      },
    });
  }
  return clientPromise;
}

async function localHealth() {
  const response = await fetch(`${LOCAL_API}/health`);
  if (!response.ok) throw new Error(`Local backend returned ${response.status}`);
  return response.json();
}

async function localAnalyze(file) {
  const form = new FormData();
  form.append("file", file, file.name || "reference.wav");
  const response = await fetch(`${LOCAL_API}/analyze`, { method: "POST", body: form });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

async function localGenerate({ text, language, refText, file }) {
  const form = new FormData();
  form.append("text", text);
  form.append("language", language);
  form.append("ref_text", refText);
  form.append("file", file, file.name || "reference.wav");
  const response = await fetch(`${LOCAL_API}/generate`, { method: "POST", body: form });
  if (!response.ok) {
    let message = `Local backend returned ${response.status}`;
    try {
      const body = await response.json();
      message = body.error || message;
    } catch (_) {}
    throw new Error(message);
  }
  return response.blob();
}

if (IS_LOCAL) {
  window.audiolabHFReady = Promise.resolve();
  window.audiolabHF = {
    health: localHealth,
    analyze: localAnalyze,
    generate: localGenerate,
  };
} else {
  window.audiolabHFReady = getHFClient();
  window.audiolabHF = {
    async health() {
      const client = await getHFClient();
      return client.view_api();
    },
    async analyze(file) {
      const client = await getHFClient();
      return client.predict("/analyze", { ref_audio: handle_file(file) });
    },
    async generate({ text, language, refText, file }) {
      const client = await getHFClient();
      return client.predict("/generate", {
        text,
        ref_audio: handle_file(file),
        ref_text: refText,
        language,
      });
    },
  };
}

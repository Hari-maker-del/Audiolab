import { Client, handle_file } from "https://cdn.jsdelivr.net/npm/@gradio/client/dist/index.min.js";

const SPACE = "ai4bharat/IndicF5";
const LOCAL_API = "http://127.0.0.1:8000";
const IS_LOCAL = ["localhost", "127.0.0.1"].includes(window.location.hostname);
let clientPromise = null;

function emitStatus(detail) {
  window.dispatchEvent(new CustomEvent("audiolab-hf-status", { detail }));
}

function timeout(promise, ms, message) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error(message)), ms)),
  ]);
}

async function getHFClient() {
  if (!clientPromise) {
    emitStatus({ stage: "connecting" });
    clientPromise = Client.connect(SPACE, {
      status_callback: (status) => emitStatus(status),
    }).then((client) => {
      emitStatus({ stage: "ready" });
      return client;
    }).catch((error) => {
      clientPromise = null;
      emitStatus({ stage: "error", error: error?.message || "Connection failed" });
      throw error;
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

async function browserAnalyze(file) {
  const context = new AudioContext();
  try {
    const buffer = await context.decodeAudioData(await file.arrayBuffer());
    const channel = buffer.getChannelData(0);
    let sum = 0, silent = 0, count = 0;
    const threshold = 0.01;
    const sampleStep = Math.max(1, Math.floor(channel.length / 50000));
    for (let i = 0; i < channel.length; i += sampleStep) {
      const v = channel[i]; sum += v * v;
      if (Math.abs(v) < threshold) silent++;
      count++;
    }
    const rms = Math.sqrt(sum / Math.max(1, count));
    const silence = silent / Math.max(1, count);
    return {
      duration: Number(buffer.duration.toFixed(2)),
      rms: Number(rms.toFixed(4)),
      silence,
      score: Math.max(0, Math.min(100, Math.round(100 - silence * 55 + Math.min(rms * 180, 35)))),
    };
  } finally { await context.close(); }
}

async function localGenerate({ text, language, refText, file }) {
  const form = new FormData();
  form.append("text", text); form.append("language", language); form.append("ref_text", refText);
  form.append("file", file, file.name || "reference.wav");
  const response = await fetch(`${LOCAL_API}/generate`, { method: "POST", body: form });
  if (!response.ok) throw new Error(`Local backend returned ${response.status}`);
  return response.blob();
}

window.audiolabHFReady = Promise.resolve();
window.audiolabHF = IS_LOCAL ? {
  health: localHealth,
  analyze: localAnalyze,
  generate: localGenerate,
} : {
  async health() {
    const client = await timeout(getHFClient(), 12000, "IndicF5 is taking too long to connect. Try Generate again.");
    return client.view_api();
  },
  async analyze(file) {
    return browserAnalyze(file);
  },
  async generate({ text, refText, file }) {
    const client = await timeout(getHFClient(), 30000, "IndicF5 connection timed out. Please try again.");
    return client.predict(text, handle_file(file), refText, { api_name: "/synthesize_speech" });
  },
};

window.addEventListener("audiolab-hf-status", (event) => {
  const stage = event.detail?.stage;
  const model = document.getElementById("modelStatus");
  const device = document.getElementById("deviceStatus");
  if (stage === "connecting") {
    if (model) model.textContent = "IndicF5 Connecting…";
    if (device) device.textContent = "Connecting when needed";
  } else if (stage === "ready") {
    if (model) model.textContent = "IndicF5 Ready";
    if (device) device.textContent = "ZeroGPU connected";
  } else if (stage === "error") {
    if (model) model.textContent = "IndicF5 Available on demand";
    if (device) device.textContent = "Retry on Generate";
  }
});

import { Client, handle_file } from "https://cdn.jsdelivr.net/npm/@gradio/client/dist/index.min.js";

const SPACE = "Hari-maker-del/audiolab-zerogpu";
let clientPromise;

async function getClient() {
  if (!clientPromise) {
    clientPromise = Client.connect(SPACE, {
      status_callback: (status) => {
        window.dispatchEvent(new CustomEvent("audiolab-hf-status", { detail: status }));
      },
    });
  }
  return clientPromise;
}

window.audiolabHFReady = getClient();
window.audiolabHF = {
  async health() {
    const client = await getClient();
    return client.view_api();
  },

  async analyze(file) {
    const client = await getClient();
    return client.predict("/analyze", {
      ref_audio: handle_file(file),
    });
  },

  async generate({ text, language, refText, file }) {
    const client = await getClient();
    return client.predict("/generate", {
      text,
      ref_audio: handle_file(file),
      ref_text: refText,
      language,
    });
  },
};

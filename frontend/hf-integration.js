// This file overrides the old local /api calls with the free Hugging Face
// ZeroGPU Space. The UI remains unchanged.

async function waitForHF() {
  if (window.audiolabHFReady) await window.audiolabHFReady;
  if (!window.audiolabHF) throw new Error("Audiolab AI backend is still loading");
  return window.audiolabHF;
}

async function handleReference(file) {
  state.reference = file;
  state.referenceName = file.name;
  const box = document.getElementById('analysisBox');
  if (box) box.innerHTML = '<div class="loading" style="margin-top:16px">Analyzing reference <i></i><i></i><i></i></div>';
  try {
    const hf = await waitForHF();
    const result = await hf.analyze(file);
    const text = result?.data?.[0] ?? '';
    const quality = result?.data?.[1] ?? 'Reference ready';
    state.analysis = { duration: 0, rms: '-', silence: 0, score: quality };
    if (box) box.innerHTML = `<div class="analysis"><div class="mini">Analysis<b>${esc(text)}</b></div><div class="mini">Quality<b class="quality">${esc(quality)}</b></div></div><div class="actions" style="margin-top:14px"><input id="voiceName" class="input" style="max-width:260px" value="My Voice"><button class="btn primary" onclick="saveVoice()">Save Voice Profile</button></div>`;
  } catch (e) {
    if (box) box.innerHTML = '<div class="dim" style="margin-top:15px">AI backend is waking up. You can still keep the reference selected and generate after the Space is ready.</div>';
  }
}

async function runGenerate() {
  if (!state.reference) { toast('Create or select a voice reference first'); return; }
  if (!document.getElementById('consent').checked) { toast('Confirm permission to use this voice'); return; }
  const text = document.getElementById('script').value.trim();
  const refText = document.getElementById('refText').value.trim();
  const language = document.getElementById('genLang').value;
  if (!text || !refText) { toast('Text and exact reference transcript are required'); return; }

  const btn = document.getElementById('generateBtn');
  const box = document.getElementById('resultBox');
  btn.disabled = true;
  btn.textContent = 'Generating…';
  box.style.display = 'block';
  box.innerHTML = '<div class="card"><div class="loading">Waking ZeroGPU and generating <i></i><i></i><i></i></div><p class="muted">The first request can take longer while the Space wakes and loads IndicF5.</p></div>';

  try {
    const hf = await waitForHF();
    const result = await hf.generate({ text, language, refText, file: state.reference });
    const fileData = result?.data?.[0];
    const audioUrl = typeof fileData === 'string' ? fileData : fileData?.url;
    if (!audioUrl) throw new Error('No audio file returned');

    const response = await fetch(audioUrl);
    if (!response.ok) throw new Error('Generated audio could not be downloaded');
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);

    box.innerHTML = `<div class="card"><div class="eyebrow">Your voice is ready</div><h3>Generated ${esc(language)} speech</h3><audio controls src="${url}"></audio><div class="actions" style="margin-top:14px"><a class="btn primary" href="${url}" download="audiolab-generated.wav">Download WAV</a><button class="btn secondary" onclick="saveGenerated('${url}','${language}')">Save to History</button></div></div>`;
    state.history.unshift({ title: text.slice(0,42) + (text.length > 42 ? '…' : ''), language, duration: 'Generated', created: new Date().toLocaleString(), url });
    state.history = state.history.slice(0, 30);
    save();
    toast('Voice generated with IndicF5');
  } catch (e) {
    console.error(e);
    box.innerHTML = `<div class="card"><strong>Generation failed</strong><p class="muted">${esc(e?.message || 'The ZeroGPU Space is unavailable or still starting. Try again shortly.')}</p></div>`;
    toast('Generation failed');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generate Voice';
  }
}

async function checkHealth() {
  const status = document.getElementById('deviceStatus');
  const api = document.getElementById('apiStatus');
  try {
    await waitForHF();
    if (status) status.textContent = 'ZeroGPU connected';
    if (api) api.textContent = 'ZeroGPU ready';
  } catch (e) {
    if (status) status.textContent = 'ZeroGPU starting';
    if (api) api.textContent = 'ZeroGPU starting';
  }
}

checkHealth();

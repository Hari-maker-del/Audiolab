(() => {
  'use strict';

  // This is a source-to-source style processor. It preserves the user's spoken
  // words and timing and applies derived delivery characteristics from the
  // uploaded style reference. It does not reproduce the reference speaker's
  // identity.
  let sourceFile = null;
  let styleFile = null;
  let sourceAudio = null;
  let styleProfile = null;
  let outputUrl = null;

  const toast = (msg) => window.toast?.(msg) || console.log(msg);
  const esc = (s) => String(s ?? '').replace(/[&<>\"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));

  function transformCard() {
    if (document.getElementById('voiceTransformCard')) return;
    const script = document.getElementById('script');
    if (!script) return;
    const card = document.createElement('div');
    card.id = 'voiceTransformCard';
    card.className = 'card';
    card.style.marginTop = '18px';
    card.innerHTML = `
      <div class="eyebrow">VOICE-OVER TRANSFORM</div>
      <h3 style="margin-top:8px">Transform your recorded voice-over</h3>
      <p class="muted">Upload the voice-over you already recorded, then upload your Tamil delivery reference. Audiolab keeps your words and original duration while applying derived comic / anti-hero delivery characteristics.</p>
      <div class="grid grid2" style="margin-top:14px">
        <div>
          <div class="label">Your voice-over</div>
          <input id="sourceVoiceover" type="file" accept="audio/*" style="display:none">
          <button id="chooseSourceVoiceover" class="btn secondary">Choose Voice-over</button>
          <div id="sourceVoiceoverInfo" class="dim" style="margin-top:8px">No source audio selected.</div>
        </div>
        <div>
          <div class="label">Tamil style reference</div>
          <div id="transformStyleInfo" class="dim">Use the style reference above, or choose it here.</div>
          <button id="chooseTransformStyle" class="btn secondary" style="margin-top:8px">Choose Style Reference</button>
        </div>
      </div>
      <div class="actions" style="margin-top:16px">
        <span id="transformProfile" class="status">Style not analyzed</span>
        <span class="dim">Output duration is preserved.</span>
      </div>
      <div class="actions" style="margin-top:16px">
        <button id="transformVoiceBtn" class="btn primary">Transform Voice-over</button>
      </div>
      <div id="transformResult" class="result"></div>
    `;
    script.parentElement.insertBefore(card, script);

    const sourceInput = card.querySelector('#sourceVoiceover');
    const styleInput = card.querySelector('#chooseTransformStyle');
    card.querySelector('#chooseSourceVoiceover').onclick = () => sourceInput.click();
    sourceInput.onchange = async () => {
      sourceFile = sourceInput.files?.[0] || null;
      if (!sourceFile) return;
      const d = await audioDuration(sourceFile).catch(() => 0);
      card.querySelector('#sourceVoiceoverInfo').textContent = `${sourceFile.name} · ${d.toFixed(1)}s`;
    };
    styleInput.onclick = () => {
      const existing = document.getElementById('styleFile');
      if (existing) existing.click();
      else {
        const temp = document.createElement('input');
        temp.type = 'file'; temp.accept = 'audio/*';
        temp.onchange = () => temp.files?.[0] && setStyleReference(temp.files[0]);
        temp.click();
      }
    };
    card.querySelector('#transformVoiceBtn').onclick = runTransform;

    const existingStyle = document.getElementById('styleFile');
    if (existingStyle) {
      existingStyle.addEventListener('change', () => existingStyle.files?.[0] && setStyleReference(existingStyle.files[0]));
    }
  }

  async function audioBuffer(file) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    const ctx = new Ctx();
    try {
      return await ctx.decodeAudioData(await file.arrayBuffer());
    } finally {
      await ctx.close();
    }
  }

  async function audioDuration(file) {
    const b = await audioBuffer(file);
    return b.duration;
  }

  function analyzeBuffer(buffer) {
    const d = buffer.getChannelData(0);
    const step = Math.max(1, Math.floor(d.length / 90000));
    let sum = 0, count = 0, crossings = 0, prev = d[0] || 0;
    let centroidNumerator = 0, centroidDenominator = 0;
    for (let i = 0; i < d.length; i += step) {
      const v = d[i];
      sum += v * v; count++;
      if ((v >= 0) !== (prev >= 0)) crossings++;
      prev = v;
    }
    // Lightweight spectral estimate from short windows.
    const fftSize = 1024;
    const bins = new Float32Array(fftSize);
    for (let start = 0; start + fftSize < d.length; start += Math.max(fftSize, Math.floor(buffer.sampleRate * 0.12))) {
      for (let i = 0; i < fftSize; i++) {
        const w = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (fftSize - 1));
        bins[i] = d[start + i] * w;
      }
      for (let k = 1; k < fftSize / 2; k++) {
        const re = bins[k];
        const mag = Math.abs(re);
        centroidNumerator += k * mag;
        centroidDenominator += mag;
      }
    }
    const rms = Math.sqrt(sum / Math.max(1, count));
    const zcr = crossings / Math.max(1, count);
    const centroid = centroidDenominator ? centroidNumerator / centroidDenominator : 0;
    return { duration: buffer.duration, rms, zcr, centroid };
  }

  async function setStyleReference(file) {
    styleFile = file;
    const card = document.getElementById('voiceTransformCard');
    if (!card) return;
    card.querySelector('#transformStyleInfo').textContent = `Analyzing ${file.name}…`;
    try {
      const b = await audioBuffer(file);
      styleProfile = analyzeBuffer(b);
      const energy = Math.min(1, Math.max(0, styleProfile.rms * 7));
      const rasp = Math.min(0.6, Math.max(0.08, styleProfile.zcr * 10));
      card.querySelector('#transformStyleInfo').textContent = `${file.name} · ${styleProfile.duration.toFixed(1)}s`;
      card.querySelector('#transformProfile').textContent = `Derived style · energy ${Math.round(energy * 100)}% · texture ${Math.round(rasp * 100)}%`;
      // Sync the existing delivery controls when available.
      const e = document.getElementById('energy');
      const r = document.getElementById('rasp');
      if (e) { e.value = String(Math.max(0.45, Math.min(0.95, energy))); e.dispatchEvent(new Event('input')); }
      if (r) { r.value = String(rasp); r.dispatchEvent(new Event('input')); }
    } catch (err) {
      card.querySelector('#transformStyleInfo').textContent = 'Could not analyze the style reference.';
      toast(err.message || 'Style analysis failed');
    }
  }

  function makeCurve(amount) {
    const n = 65536, curve = new Float32Array(n);
    const drive = 1 + amount * 7;
    for (let i = 0; i < n; i++) {
      const x = (i * 2) / (n - 1) - 1;
      curve[i] = Math.tanh(x * drive) / Math.tanh(drive);
    }
    return curve;
  }

  async function renderTransform(source, profile) {
    const sr = source.sampleRate;
    const ctx = new OfflineAudioContext(1, source.length, sr);
    const src = ctx.createBufferSource();
    src.buffer = source;

    const high = ctx.createBiquadFilter();
    high.type = 'highpass'; high.frequency.value = 70;

    const body = ctx.createBiquadFilter();
    body.type = 'peaking'; body.frequency.value = 180; body.Q.value = 0.9;
    body.gain.value = 1.5 + Math.min(3, profile.rms * 12);

    const presence = ctx.createBiquadFilter();
    presence.type = 'peaking'; presence.frequency.value = 2100; presence.Q.value = 0.8;
    presence.gain.value = 2.0 + Math.min(4, profile.zcr * 16);

    const air = ctx.createBiquadFilter();
    air.type = 'highshelf'; air.frequency.value = 5500;
    air.gain.value = Math.min(3.5, 0.8 + profile.centroid / 160);

    const compressor = ctx.createDynamicsCompressor();
    compressor.threshold.value = -18;
    compressor.knee.value = 16;
    compressor.ratio.value = 3.5;
    compressor.attack.value = 0.004;
    compressor.release.value = 0.09;

    const saturator = ctx.createWaveShaper();
    const rasp = Math.min(0.55, Math.max(0.08, profile.zcr * 11));
    saturator.curve = makeCurve(rasp);
    saturator.oversample = '2x';

    const output = ctx.createGain();
    output.gain.value = 0.92;

    src.connect(high).connect(body).connect(presence).connect(air).connect(compressor).connect(saturator).connect(output).connect(ctx.destination);
    src.start(0);
    return await ctx.startRendering();
  }

  function wavBlob(buffer) {
    const ch = buffer.getChannelData(0);
    const bytes = new ArrayBuffer(44 + ch.length * 2);
    const view = new DataView(bytes);
    const write = (offset, text) => [...text].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
    write(0, 'RIFF'); view.setUint32(4, 36 + ch.length * 2, true); write(8, 'WAVE');
    write(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
    view.setUint32(24, buffer.sampleRate, true); view.setUint32(28, buffer.sampleRate * 2, true);
    view.setUint16(32, 2, true); view.setUint16(34, 16, true); write(36, 'data'); view.setUint32(40, ch.length * 2, true);
    let p = 44;
    for (let i = 0; i < ch.length; i++, p += 2) {
      const v = Math.max(-1, Math.min(1, ch[i]));
      view.setInt16(p, v < 0 ? v * 0x8000 : v * 0x7fff, true);
    }
    return new Blob([bytes], {type: 'audio/wav'});
  }

  async function runTransform() {
    const result = document.getElementById('transformResult');
    if (!result) return;
    const consent = document.getElementById('consent');
    if (!consent?.checked) { toast('Confirm authorized use of your own voice first.'); return; }
    if (!sourceFile) { toast('Choose your recorded voice-over first.'); return; }
    if (!styleFile) {
      const existing = document.getElementById('styleFile');
      if (existing?.files?.[0]) await setStyleReference(existing.files[0]);
    }
    if (!styleFile || !styleProfile) { toast('Choose a Tamil style reference first.'); return; }
    const button = document.getElementById('transformVoiceBtn');
    button.disabled = true; button.textContent = 'Transforming…';
    result.innerHTML = '<div class="loading">Processing the full voice-over locally…</div>';
    try {
      sourceAudio = await audioBuffer(sourceFile);
      const rendered = await renderTransform(sourceAudio, styleProfile);
      const blob = wavBlob(rendered);
      if (outputUrl) URL.revokeObjectURL(outputUrl);
      outputUrl = URL.createObjectURL(blob);
      result.innerHTML = `<div class="card" style="margin-top:14px;padding:16px"><div class="eyebrow">TRANSFORM COMPLETE</div><h3 style="margin-top:8px">Your voice-over is ready</h3><p class="muted">Original duration: ${sourceAudio.duration.toFixed(2)}s · Output duration: ${rendered.duration.toFixed(2)}s</p><audio controls style="width:100%;margin-top:12px" src="${outputUrl}"></audio><div class="actions" style="margin-top:12px"><a class="btn primary" href="${outputUrl}" download="audiolab-tamil-style-voiceover.wav">Download WAV</a></div></div>`;
      toast('Voice-over transformed successfully.');
    } catch (err) {
      result.innerHTML = `<div class="dim">Transform failed: ${esc(err.message || err)}</div>`;
      toast('Voice transformation failed.');
    } finally {
      button.disabled = false; button.textContent = 'Transform Voice-over';
    }
  }

  function install() {
    transformCard();
    const style = document.getElementById('styleFile');
    if (style && !style.dataset.transformHooked) {
      style.dataset.transformHooked = '1';
      style.addEventListener('change', () => style.files?.[0] && setStyleReference(style.files[0]));
    }
  }

  const observer = new MutationObserver(() => {
    if (document.getElementById('script')) install();
  });
  observer.observe(document.body, {childList: true, subtree: true});
  window.addEventListener('load', install);
  setTimeout(install, 300);
})();

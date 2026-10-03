(() => {
  const toast = (message) => {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = message;
    el.classList.add('show');
    clearTimeout(window.__audiolabToastTimer);
    window.__audiolabToastTimer = setTimeout(() => el.classList.remove('show'), 2800);
  };

  function ensureToolWorkspace() {
    const page = document.getElementById('page-tools');
    if (!page) return null;
    let host = document.getElementById('proEditor');
    if (!host) {
      host = document.createElement('div');
      host.id = 'proEditor';
      page.appendChild(host);
    }
    return host;
  }

  function openTool(name) {
    const host = ensureToolWorkspace();
    if (!host) return;
    host.scrollIntoView({ behavior: 'smooth', block: 'start' });
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'audio/*';
    input.style.display = 'none';
    document.body.appendChild(input);
    input.onchange = () => {
      const file = input.files?.[0];
      input.remove();
      if (!file) return;
      if (typeof window.__audiolabAddToolFile === 'function') {
        window.__audiolabAddToolFile(file, name);
      } else {
        toast(`${name}: Audio Studio is opening…`);
        window.nav?.('tools');
      }
    };
    input.click();
  }

  function installBrowserEditor() {
    const host = document.getElementById('proEditor');
    if (!host || host.dataset.browserEditor === '1') return;
    host.dataset.browserEditor = '1';
    let file = null;
    let audioBuffer = null;
    let objectUrl = null;

    host.innerHTML = `
      <div class="card" style="margin-top:18px">
        <div class="eyebrow">FREE BROWSER AUDIO WORKSPACE</div>
        <h2 style="margin:8px 0">Audio Studio</h2>
        <p class="muted">Runs directly in your browser. No RunPod, no paid backend required.</p>
        <div class="actions" style="margin-top:14px">
          <button class="btn primary" id="browserAudioChoose">Choose Audio</button>
          <button class="btn secondary" id="browserAudioPlay" disabled>Play</button>
          <button class="btn secondary" id="browserAudioDownload" disabled>Download Original</button>
        </div>
        <div id="browserAudioInfo" class="dim" style="margin-top:12px">No audio selected.</div>
        <div class="grid grid3" style="margin-top:16px">
          <button class="btn secondary" data-browser-effect="normalize" disabled>Normalize</button>
          <button class="btn secondary" data-browser-effect="silence" disabled>Remove Silence</button>
          <button class="btn secondary" data-browser-effect="noise" disabled>Noise Gate</button>
          <button class="btn secondary" data-browser-effect="speed" disabled>Speed 1.05×</button>
          <button class="btn secondary" data-browser-effect="speedslow" disabled>Speed 0.90×</button>
          <button class="btn secondary" data-browser-effect="export" disabled>Export WAV</button>
        </div>
        <audio id="browserAudioPlayer" controls style="width:100%;margin-top:16px;display:none"></audio>
      </div>`;

    const choose = document.getElementById('browserAudioChoose');
    const player = document.getElementById('browserAudioPlayer');
    const info = document.getElementById('browserAudioInfo');
    const play = document.getElementById('browserAudioPlay');
    const download = document.getElementById('browserAudioDownload');
    const effects = [...host.querySelectorAll('[data-browser-effect]')];

    const selectFile = () => {
      const i = document.createElement('input');
      i.type = 'file'; i.accept = 'audio/*';
      i.onchange = () => i.files?.[0] && loadFile(i.files[0]);
      i.click();
    };

    async function loadFile(next) {
      file = next;
      objectUrl && URL.revokeObjectURL(objectUrl);
      objectUrl = URL.createObjectURL(file);
      player.src = objectUrl;
      player.style.display = 'block';
      play.disabled = false;
      download.disabled = false;
      effects.forEach(x => x.disabled = false);
      info.textContent = `Loaded: ${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
      try {
        const ctx = new AudioContext();
        audioBuffer = await ctx.decodeAudioData(await file.arrayBuffer());
        info.textContent = `Loaded: ${file.name} · ${audioBuffer.duration.toFixed(2)}s · ${audioBuffer.sampleRate} Hz`;
        await ctx.close();
      } catch (_) {}
    }

    async function renderEffect(kind) {
      if (!audioBuffer) return toast('Choose an audio file first.');
      toast(`Applying ${kind}…`);
      const rate = kind === 'speed' ? 1.05 : kind === 'speedslow' ? 0.90 : 1;
      const length = Math.max(1, Math.ceil(audioBuffer.length / rate));
      const ctx = new OfflineAudioContext(audioBuffer.numberOfChannels, length, audioBuffer.sampleRate);
      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.playbackRate.value = rate;
      const gain = ctx.createGain();
      if (kind === 'normalize') {
        let peak = 0;
        for (let c = 0; c < audioBuffer.numberOfChannels; c++) {
          const data = audioBuffer.getChannelData(c);
          for (let i = 0; i < data.length; i += 64) peak = Math.max(peak, Math.abs(data[i]));
        }
        gain.gain.value = peak > 0 ? Math.min(4, 0.92 / peak) : 1;
      } else if (kind === 'noise') {
        const shaper = ctx.createWaveShaper();
        const curve = new Float32Array(65536);
        for (let i = 0; i < curve.length; i++) {
          const x = i * 2 / (curve.length - 1) - 1;
          curve[i] = Math.abs(x) < 0.025 ? 0 : x;
        }
        shaper.curve = curve;
        source.connect(shaper).connect(gain).connect(ctx.destination);
        source.start();
        audioBuffer = await ctx.startRendering();
        await replaceRendered(audioBuffer, `${kind}`);
        return;
      }
      source.connect(gain).connect(ctx.destination);
      source.start();
      audioBuffer = await ctx.startRendering();
      await replaceRendered(audioBuffer, kind);
    }

    async function replaceRendered(buffer, suffix) {
      const wav = encodeWav(buffer);
      const blob = new Blob([wav], { type: 'audio/wav' });
      file = new File([blob], `${file.name.replace(/\.[^.]+$/, '')}-${suffix}.wav`, { type: 'audio/wav' });
      objectUrl && URL.revokeObjectURL(objectUrl);
      objectUrl = URL.createObjectURL(file);
      player.src = objectUrl;
      player.style.display = 'block';
      download.disabled = false;
      download.onclick = () => saveBlob(blob, file.name);
      info.textContent = `Processed: ${file.name} · ${buffer.duration.toFixed(2)}s`;
      toast(`${suffix} complete`);
    }

    function saveBlob(blob, name) {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = name; a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    }

    function encodeWav(buffer) {
      const channels = buffer.numberOfChannels;
      const length = buffer.length * channels * 2 + 44;
      const view = new DataView(new ArrayBuffer(length));
      const write = (offset, text) => [...text].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
      write(0, 'RIFF'); view.setUint32(4, 36 + buffer.length * channels * 2, true); write(8, 'WAVE');
      write(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
      view.setUint16(22, channels, true); view.setUint32(24, buffer.sampleRate, true);
      view.setUint32(28, buffer.sampleRate * channels * 2, true); view.setUint16(32, channels * 2, true);
      view.setUint16(34, 16, true); write(36, 'data'); view.setUint32(40, buffer.length * channels * 2, true);
      let pos = 44;
      for (let i = 0; i < buffer.length; i++) for (let c = 0; c < channels; c++) {
        const v = Math.max(-1, Math.min(1, buffer.getChannelData(c)[i]));
        view.setInt16(pos, v < 0 ? v * 0x8000 : v * 0x7fff, true); pos += 2;
      }
      return view;
    }

    choose.onclick = selectFile;
    play.onclick = () => player.play();
    download.onclick = () => file && saveBlob(file, file.name);
    effects.forEach(btn => btn.onclick = () => {
      const kind = btn.dataset.browserEffect;
      if (kind === 'export') return file && saveBlob(file, file.name);
      renderEffect(kind);
    });

    window.__audiolabAddToolFile = (next) => loadFile(next);
  }

  document.addEventListener('click', (event) => {
    const tool = event.target.closest?.('[data-action="tool"]');
    if (tool) {
      event.preventDefault();
      event.stopImmediatePropagation();
      const card = tool.closest('.tool');
      const name = card?.querySelector('h3')?.textContent || 'Audio Tool';
      window.nav?.('tools');
      setTimeout(() => { installBrowserEditor(); openTool(name); }, 50);
    }
  }, true);

  const observer = new MutationObserver(() => {
    if (document.getElementById('page-tools')?.classList.contains('active')) {
      ensureToolWorkspace();
      installBrowserEditor();
    }
  });
  observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
  document.addEventListener('DOMContentLoaded', () => setTimeout(() => {
    if (document.getElementById('page-tools')?.classList.contains('active')) installBrowserEditor();
  }, 100));
})();

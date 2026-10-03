(() => {
  const API = window.AUDIOLAB_API_URL || 'http://127.0.0.1:8000';
  const tracks = [];
  let selected = -1;
  let selection = { start: 0, end: 0 };
  let player = null;

  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
  const toast = (m) => window.toast ? window.toast(m) : alert(m);
  const current = () => tracks[selected];

  function mount() {
    const page = document.getElementById('page-tools');
    const host = document.getElementById('proEditor');
    if (!page || !host || !page.classList.contains('active')) return;
    if (host.dataset.phase1Mounted === '1') return;
    host.dataset.phase1Mounted = '1';
    render();
  }

  function render() {
    const host = document.getElementById('proEditor');
    if (!host) return;
    const t = current();
    host.innerHTML = `
      <div class="card pro-editor">
        <div class="timeline-toolbar">
          <button id="studioAdd" class="btn primary">＋ Add Audio</button>
          <button id="studioPlay" class="btn secondary">▶ Play</button>
          <button id="studioStop" class="btn secondary">■ Stop</button>
          <button id="studioTrim" class="btn secondary">✂ Trim Selection</button>
          <button id="studioUndo" class="btn secondary">↶ Clear Selection</button>
          <button id="studioExport" class="btn primary">⇩ Export</button>
        </div>
        <div class="editor-status"><span class="status">${t ? `Track ${selected + 1}: ${esc(t.name)}` : 'No audio loaded'}</span><span class="dim">Select a region, then apply an effect.</span></div>
        <div class="selection-bar">
          <label>Start <input id="studioStart" type="number" min="0" step="0.01" value="${selection.start.toFixed(2)}"></label>
          <label>End <input id="studioEnd" type="number" min="0" step="0.01" value="${selection.end.toFixed(2)}"></label>
          <span>Duration: ${Math.max(0, selection.end - selection.start).toFixed(2)}s</span>
        </div>
        <div class="timeline" id="studioTimeline">
          ${tracks.length ? tracks.map((x, i) => `
            <div class="track-row ${i === selected ? 'track-selected' : ''}" data-track="${i}">
              <div class="track-controls"><strong>${esc(x.name)}</strong><small>${x.duration.toFixed(2)}s</small></div>
              <div class="lane"><div class="clip-pro ${i === selected ? 'selected' : ''}" data-clip="${i}" style="width:${Math.max(220, x.duration * 45)}px"><canvas data-wave="${i}"></canvas></div></div>
            </div>`).join('') : '<div class="empty"><strong>Start your audio project</strong><br><span class="muted">Add WAV, MP3, M4A, FLAC or browser-supported audio.</span></div>'}
        </div>
        <div class="effect-rack">
          ${[['normalize','Normalize'],['eq','EQ'],['compress','Compressor'],['noise-reduce','Noise Reduction'],['reverb','Reverb'],['enhance','Voice Enhance'],['speed','Speed'],['pitch','Pitch']].map(([k,l]) => `<div class="effect"><b>${l}</b><small>Backend processing</small><button data-effect="${k}">Apply</button></div>`).join('')}
        </div>
      </div>`;
    bind();
    drawWaveforms();
  }

  function bind() {
    document.getElementById('studioAdd')?.addEventListener('click', () => {
      const input = document.createElement('input');
      input.type = 'file'; input.accept = 'audio/*'; input.multiple = true;
      input.onchange = () => [...input.files].forEach(addFile);
      input.click();
    });
    document.getElementById('studioPlay')?.addEventListener('click', () => play(true));
    document.getElementById('studioStop')?.addEventListener('click', stop);
    document.getElementById('studioTrim')?.addEventListener('click', trim);
    document.getElementById('studioUndo')?.addEventListener('click', () => { selection = { start: 0, end: current()?.duration || 0 }; render(); });
    document.getElementById('studioExport')?.addEventListener('click', exportTrack);
    document.getElementById('studioStart')?.addEventListener('change', e => { selection.start = Math.max(0, Number(e.target.value) || 0); if (selection.end < selection.start) selection.end = selection.start; });
    document.getElementById('studioEnd')?.addEventListener('change', e => { selection.end = Math.max(selection.start, Number(e.target.value) || 0); });
    document.querySelectorAll('[data-clip]').forEach(el => el.addEventListener('click', () => { selected = Number(el.dataset.clip); const t = current(); selection = { start: 0, end: t.duration }; render(); }));
    document.querySelectorAll('[data-effect]').forEach(el => el.addEventListener('click', () => process(el.dataset.effect)));
  }

  function addFile(file) {
    const audio = new Audio(URL.createObjectURL(file));
    audio.onloadedmetadata = () => {
      tracks.push({ file, name: file.name, duration: audio.duration });
      selected = tracks.length - 1;
      selection = { start: 0, end: audio.duration };
      render();
    };
  }

  async function drawWaveforms() {
    for (const canvas of document.querySelectorAll('[data-wave]')) {
      const t = tracks[Number(canvas.dataset.wave)];
      if (!t) continue;
      try {
        const audio = await new AudioContext().decodeAudioData(await t.file.arrayBuffer());
        const data = audio.getChannelData(0);
        const width = Math.max(300, Math.floor(t.duration * 45));
        canvas.width = width; canvas.height = 56;
        const ctx = canvas.getContext('2d'); const step = Math.max(1, Math.floor(data.length / width));
        ctx.fillStyle = 'rgba(230,185,74,.72)';
        for (let x = 0; x < width; x++) {
          let min = 1, max = -1;
          for (let j = 0; j < step && x * step + j < data.length; j++) { const v = data[x * step + j]; min = Math.min(min, v); max = Math.max(max, v); }
          ctx.fillRect(x, (1 + min) * 28, 1, Math.max(1, (max - min) * 28));
        }
      } catch (_) {}
    }
  }

  function play(range) {
    const t = current(); if (!t) return toast('Add an audio file first.');
    stop(); player = new Audio(URL.createObjectURL(t.file));
    player.currentTime = range ? Math.min(selection.start, t.duration) : 0;
    player.play();
    if (range) player.ontimeupdate = () => { if (player.currentTime >= selection.end) stop(); };
    player.onended = () => { player = null; };
  }
  function stop() { if (player) { player.pause(); player.currentTime = 0; player = null; } }

  async function process(operation) {
    const t = current(); if (!t) return toast('Add an audio file first.');
    const fd = new FormData(); fd.append('file', t.file, t.name);
    fd.append('start', String(selection.start)); fd.append('end', String(selection.end));
    if (operation === 'speed') fd.append('rate', '1.05');
    if (operation === 'pitch') fd.append('semitones', '1');
    if (operation === 'noise-reduce') fd.append('strength', '.65');
    if (operation === 'reverb') { fd.append('mix', '.18'); fd.append('decay', '.55'); }
    if (operation === 'compress') { fd.append('threshold_db', '-18'); fd.append('ratio', '3'); }
    try {
      toast(`Processing ${operation}…`);
      const response = await fetch(`${API}/edit/${operation}`, { method: 'POST', body: fd });
      if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`);
      const blob = await response.blob();
      const file = new File([blob], t.name.replace(/\.[^.]+$/, '') + `-${operation}.wav`, { type: 'audio/wav' });
      const a = new Audio(URL.createObjectURL(file));
      await new Promise((resolve, reject) => { a.onloadedmetadata = resolve; a.onerror = reject; });
      tracks[selected] = { file, name: file.name, duration: a.duration };
      selection = { start: 0, end: a.duration };
      render(); toast(`${operation} applied`);
    } catch (e) { toast(`Processing failed: ${e.message}`); }
  }

  async function trim() {
    if (!current()) return toast('Add an audio file first.');
    if (selection.end <= selection.start) return toast('Select a valid region.');
    await process('trim');
  }

  function exportTrack() {
    const t = current(); if (!t) return toast('Add an audio file first.');
    const a = document.createElement('a'); a.href = URL.createObjectURL(t.file); a.download = t.name; a.click();
  }

  const observer = new MutationObserver(mount);
  observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
  document.addEventListener('DOMContentLoaded', mount);
  setTimeout(mount, 250);
})();

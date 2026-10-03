(() => {
  const state = {
    page: 'studio', reference: null, referenceName: '', analysis: null,
    history: JSON.parse(localStorage.getItem('audiolab-history') || '[]'),
    voices: JSON.parse(localStorage.getItem('audiolab-voices') || '[]')
  };
  const pages = ['studio','voices','generate','history','tools','models','settings'];
  const langs = ['Tamil','Telugu','Malayalam','Hindi','Kannada','Bengali','Gujarati','Marathi','Odia','Punjabi','Assamese'];
  const esc = s => String(s ?? '').replace(/[&<>\"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  const toast = msg => { const el = document.getElementById('toast'); if (!el) return; el.textContent = msg; el.classList.add('show'); setTimeout(() => el.classList.remove('show'), 2600); };
  const save = () => { localStorage.setItem('audiolab-history', JSON.stringify(state.history)); localStorage.setItem('audiolab-voices', JSON.stringify(state.voices)); };

  function nav(page) {
    if (!pages.includes(page)) return;
    state.page = page;
    pages.forEach(p => document.getElementById('page-' + p)?.classList.toggle('active', p === page));
    document.querySelectorAll('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.page === page));
    renderPage();
    window.scrollTo({top:0, behavior:'smooth'});
    document.querySelector('.sidebar')?.classList.remove('open');
  }
  window.nav = nav;

  function studio() {
    return `<div class="hero"><div><div class="eyebrow">Audiolab / Studio</div><h1>Create speech that sounds like you.</h1><p>Your voice. Your language. Your sound. A local-first Indian-language AI audio workspace.</p><div class="actions"><button class="btn primary" data-action="go-generate">Create Voice</button><button class="btn secondary" data-action="go-voices">Upload Reference</button></div></div></div>
      <div class="card wave-card"><span class="status"><span class="dot"></span> IndicF5 · Indian languages</span><h3 style="margin-top:15px">Ready to create?</h3><p class="muted">Reference → Script → Generate → Preview → Export</p><div class="actions"><button class="btn secondary" data-action="go-voices">Start with a reference recording</button></div></div>
      <div class="grid grid3" style="margin-top:16px"><div class="card"><div class="eyebrow">Voice profile</div><h3 style="margin-top:12px">${esc(state.voices[0]?.name || 'No voice yet')}</h3><p class="muted">${state.voices.length ? 'Ready to generate' : 'Create your first voice profile.'}</p><button class="btn secondary" data-action="go-voices">${state.voices.length ? 'Use Voice' : 'Create Voice'}</button></div>
      <div class="card"><div class="eyebrow">Recent generation</div><h3 style="margin-top:12px">${esc(state.history[0]?.title || 'No generations yet')}</h3><p class="muted">${state.history.length ? esc(state.history[0].language) : 'Generate your first clip.'}</p><button class="btn secondary" data-action="go-history">Open History</button></div>
      <div class="card"><div class="eyebrow">AI model</div><h3 style="margin-top:12px">IndicF5</h3><p class="muted">11 Indian languages · Hugging Face ZeroGPU</p><span class="status" id="modelStatus">Checking model…</span></div></div>`;
  }

  function voices() {
    return `<div class="hero"><div><div class="eyebrow">Voice profiles</div><h1>Your Voice</h1><p>Use recordings you own or have explicit permission to use.</p></div><button class="btn primary" data-action="choose-file">Upload Recording</button></div>
      <div class="card"><div class="upload"><strong>Drop or select a reference recording</strong><span class="muted">WAV, MP3 or browser-supported audio. A clean 3–10 second single-speaker clip works well.</span><input id="voiceFile" type="file" accept="audio/*" style="display:none"><div class="actions"><button class="btn secondary" data-action="choose-file">Choose Audio</button><button class="btn ghost" data-action="record">Record Voice</button></div><div id="recordBox"></div></div><div id="analysisBox"></div></div>
      <div style="height:16px"></div><div class="grid" id="voiceList">${state.voices.length ? state.voices.map((v,i) => `<div class="voice-row"><div class="avatar">${esc(v.name.slice(0,1).toUpperCase())}</div><div class="row-main"><strong>${esc(v.name)}</strong><span class="muted">${esc(v.language || 'Tamil')} · ${esc(v.duration || 'Reference')}</span></div><span class="status">Ready</span><button class="btn secondary" data-use-voice="${i}">Generate</button></div>`).join('') : '<div class="empty">No voice profiles yet.<br><br><button class="btn primary" data-action="choose-file">Create your first voice</button></div>'}</div>`;
  }

  function generate() {
    return `<div class="hero"><div><div class="eyebrow">Generation studio</div><h1>Generate speech</h1><p>Enter your script and the exact transcript of your authorized reference recording.</p></div></div>
      <div class="card form-card"><div class="grid grid2"><div><div class="label">Voice</div><select id="genVoice" class="select">${state.voices.length ? state.voices.map((x,i) => `<option value="${i}">${esc(x.name)}</option>`).join('') : '<option>No voice profile — create one first</option>'}</select></div><div><div class="label">Language</div><select id="genLang" class="select">${langs.map(x => `<option>${x}</option>`).join('')}</select></div></div>
      <div class="label">Input mode</div><div class="actions"><button class="btn secondary" data-action="tamil">தமிழ் Tamil</button><button class="btn ghost" data-action="tanglish">Tanglish</button></div>
      <div class="label">Script</div><textarea id="script" class="textarea" maxlength="5000" placeholder="உங்கள் உரையை இங்கே உள்ளிடுங்கள்...">வணக்கம் நண்பர்களே! இன்று நம்முடைய புதிய பயணத்தை ஆரம்பிக்கலாம்.</textarea>
      <div class="label">Reference transcript</div><textarea id="refText" class="textarea" style="min-height:130px" placeholder="Type exactly what is spoken in your reference recording."></textarea>
      <div class="consent" style="margin-top:16px"><input id="consent" type="checkbox"><span>I confirm I have permission to use this voice.</span></div>
      <div class="actions" style="margin-top:16px"><button id="generateBtn" class="btn primary" data-action="generate" ${state.voices.length ? '' : 'disabled'}>Generate Voice</button><button class="btn secondary" data-action="go-voices">Manage Voice</button></div><div id="resultBox" class="result"></div></div>`;
  }

  function historyPage() { return `<div class="hero"><div><div class="eyebrow">History</div><h1>Generation History</h1><p>Your recent generations.</p></div><button class="btn secondary" data-action="clear-history">Clear History</button></div><div class="grid">${state.history.length ? state.history.map((h,i) => `<div class="history-row"><div class="avatar">≈</div><div class="row-main"><strong>${esc(h.title)}</strong><span class="muted">${esc(h.language)} · ${esc(h.created)}</span></div><button class="btn secondary" data-play="${i}">Play</button></div>`).join('') : '<div class="empty">No generations yet.<br><br><button class="btn primary" data-action="go-generate">Generate Speech</button></div>'}</div>`; }
  function tools() { return `<div class="hero"><div><div class="eyebrow">Audio tools</div><h1>Professional audio tools.</h1><p>Focused utilities around the voice-generation workflow.</p></div></div><div class="grid grid3">${[['Voice Converter','Convert authorized speech.'],['Audio Cleaner','Prepare a cleaner reference.'],['Noise Reduction','Reduce background noise.'],['Silence Remover','Remove unwanted silence.'],['Pitch / Speed','Fine-tune audio.'],['Audio Format','Prepare exports.']].map(t => `<div class="card tool"><h3>${t[0]}</h3><p class="muted">${t[1]}</p><button class="btn secondary" data-action="tool">Open Tool</button></div>`).join('')}</div>`; }
  function models() { return `<div class="hero"><div><div class="eyebrow">AI models</div><h1>Model control.</h1><p>IndicF5 is the primary Indian-language voice model.</p></div></div><div class="grid grid2"><div class="card"><span class="status">Indian Languages</span><h3 style="margin-top:15px">IndicF5</h3><p class="muted">Tamil, Telugu, Malayalam, Hindi, Kannada, Bengali, Gujarati, Marathi, Odia, Punjabi and Assamese.</p><span id="apiStatus" class="status">Checking…</span></div></div>`; }
  function settings() { return `<div class="hero"><div><div class="eyebrow">Settings</div><h1>Audiolab preferences.</h1><p>Local workspace controls.</p></div></div><div class="grid grid2"><div class="card"><h3>General</h3><div class="label">Default language</div><select class="select">${langs.map(x => `<option>${x}</option>`).join('')}</select><div class="label">Export</div><select class="select"><option>WAV</option><option>MP3</option><option>FLAC</option></select></div><div class="card"><h3>Privacy</h3><p class="muted">Only use voice recordings you own or have permission to use.</p><button class="btn secondary" data-action="clear-data">Clear Local Data</button></div></div>`; }

  function renderPage() {
    const html = {studio:studio, voices:voices, generate:generate, history:historyPage, tools:tools, models:models, settings:settings};
    pages.forEach(p => { const el = document.getElementById('page-' + p); if (el && p === state.page) el.innerHTML = html[p](); });
    bindPage();
    checkHealth();
  }

  function bindPage() {
    document.querySelectorAll('.nav-item').forEach(b => { b.onclick = e => { e.preventDefault(); nav(b.dataset.page); }; });
    const menu = document.getElementById('menuBtn'); if (menu) menu.onclick = () => document.querySelector('.sidebar')?.classList.toggle('open');
    document.querySelectorAll('[data-action]').forEach(el => el.onclick = () => {
      const a = el.dataset.action;
      if (a === 'go-generate') nav('generate');
      else if (a === 'go-voices' || a === 'choose-file') document.getElementById('voiceFile')?.click() || nav('voices');
      else if (a === 'go-history') nav('history');
      else if (a === 'record') startRecord();
      else if (a === 'generate') runGenerate();
      else if (a === 'tamil') toast('Tamil mode selected');
      else if (a === 'tanglish') { const s=document.getElementById('script'); if(s) s.placeholder='Vanakkam nanbargale, eppadi irukeenga?'; toast('Tanglish mode selected'); }
      else if (a === 'clear-history') { state.history=[]; save(); renderPage(); }
      else if (a === 'clear-data') { localStorage.removeItem('audiolab-history'); localStorage.removeItem('audiolab-voices'); location.reload(); }
      else if (a === 'tool') toast('Tool workspace will be connected to the free browser pipeline next.');
    });
    const file = document.getElementById('voiceFile'); if (file) file.onchange = () => file.files[0] && handleReference(file.files[0]);
    document.querySelectorAll('[data-use-voice]').forEach(el => el.onclick = () => { nav('generate'); });
    document.querySelectorAll('[data-play]').forEach(el => el.onclick = () => playHistory(Number(el.dataset.play)));
  }

  async function waitHF() {
    if (window.audiolabHFReady) await window.audiolabHFReady;
    if (!window.audiolabHF) throw new Error('AI client is still loading. Refresh once and try again.');
    return window.audiolabHF;
  }

  async function handleReference(file) {
    state.reference = file; state.referenceName = file.name;
    const box = document.getElementById('analysisBox'); if (!box) return;
    box.innerHTML = '<div class="loading" style="margin-top:16px">Analyzing reference…</div>';
    try {
      const hf = await waitHF(); const result = await hf.analyze(file); state.analysis = result;
      box.innerHTML = `<div class="analysis"><div class="mini">Duration<b>${esc(result.duration)}s</b></div><div class="mini">RMS<b>${esc(result.rms)}</b></div><div class="mini">Silence<b>${Math.round(result.silence*100)}%</b></div><div class="mini">Quality<b class="quality">${esc(result.score)}/100</b></div></div><div class="actions" style="margin-top:14px"><input id="voiceName" class="input" style="max-width:260px" value="My Voice"><button class="btn primary" id="saveVoiceBtn">Save Voice Profile</button></div>`;
      document.getElementById('saveVoiceBtn').onclick = saveVoice;
    } catch (e) { box.innerHTML = `<div class="dim" style="margin-top:15px">Reference selected. ${esc(e.message || 'Analysis unavailable')}.</div><div class="actions" style="margin-top:14px"><input id="voiceName" class="input" style="max-width:260px" value="My Voice"><button class="btn primary" id="saveVoiceBtn">Save Voice Profile</button></div>`; document.getElementById('saveVoiceBtn').onclick = saveVoice; }
  }
  function saveVoice() { const name = document.getElementById('voiceName')?.value.trim() || 'My Voice'; state.voices.unshift({name, language:'Tamil', duration:(state.analysis?.duration || 0)+' sec', fileName:state.referenceName}); state.voices=state.voices.slice(0,10); save(); toast('Voice profile saved'); nav('voices'); }

  let recorder, stream, chunks=[];
  async function startRecord() { if (!navigator.mediaDevices?.getUserMedia) return toast('Microphone is not supported here.'); try { stream=await navigator.mediaDevices.getUserMedia({audio:true}); chunks=[]; recorder=new MediaRecorder(stream); recorder.ondataavailable=e=>e.data.size&&chunks.push(e.data); recorder.onstop=async()=>{ const file=new File([new Blob(chunks,{type:'audio/webm'})],'audiolab-recording.webm',{type:'audio/webm'}); stream.getTracks().forEach(t=>t.stop()); await handleReference(file); }; recorder.start(); document.getElementById('recordBox').innerHTML='<div class="actions" style="margin-top:15px"><span class="status">● Recording</span><button class="btn secondary" id="stopRecord">Stop</button></div>'; document.getElementById('stopRecord').onclick=()=>recorder.stop(); } catch(e) { toast('Microphone permission was not granted'); } }

  async function runGenerate() {
    if (!state.reference) return toast('Upload or record a voice reference first');
    if (!document.getElementById('consent')?.checked) return toast('Confirm permission to use this voice');
    const text=document.getElementById('script')?.value.trim(), refText=document.getElementById('refText')?.value.trim(), language=document.getElementById('genLang')?.value || 'Tamil';
    if (!text || !refText) return toast('Script and exact reference transcript are required');
    const btn=document.getElementById('generateBtn'), box=document.getElementById('resultBox'); btn.disabled=true; btn.textContent='Generating…'; box.innerHTML='<div class="card"><div class="loading">Generating with IndicF5…</div></div>';
    try {
      const hf=await waitHF(); const result=await hf.generate({text,language,refText,file:state.reference});
      let fileData=result?.data?.[0]; let audioUrl=typeof fileData==='string'?fileData:fileData?.url;
      if (!audioUrl && result?.url) audioUrl=result.url;
      if (!audioUrl) throw new Error('No audio file was returned by IndicF5.');
      const response=await fetch(audioUrl); if(!response.ok) throw new Error('Generated audio could not be downloaded.');
      const blob=await response.blob(), url=URL.createObjectURL(blob);
      box.innerHTML=`<div class="card"><div class="eyebrow">Your voice is ready</div><h3>Generated ${esc(language)} speech</h3><audio controls src="${url}" style="width:100%;margin-top:12px"></audio><div class="actions" style="margin-top:14px"><a class="btn primary" href="${url}" download="audiolab-generated.wav">Download WAV</a><button class="btn secondary" id="saveGenerated">Save to History</button></div></div>`;
      state.history.unshift({title:text.slice(0,42)+(text.length>42?'…':''),language,created:new Date().toLocaleString(),url}); state.history=state.history.slice(0,30); save(); document.getElementById('saveGenerated').onclick=()=>toast('Saved to History'); toast('Voice generated');
    } catch(e) { box.innerHTML=`<div class="card"><strong>Generation failed</strong><p class="muted">${esc(e.message || 'IndicF5 request failed.')}</p></div>`; toast('Generation failed'); }
    finally { btn.disabled=false; btn.textContent='Generate Voice'; }
  }

  async function checkHealth() { try { const hf=await waitHF(); await hf.health(); document.getElementById('deviceStatus')?.replaceChildren(document.createTextNode('ZeroGPU connected')); document.getElementById('modelStatus')?.replaceChildren(document.createTextNode('IndicF5 Ready')); document.getElementById('apiStatus')?.replaceChildren(document.createTextNode('ZeroGPU ready')); } catch(_) { document.getElementById('deviceStatus')?.replaceChildren(document.createTextNode('AI client loading…')); } }
  function playHistory(i) { const h=state.history[i]; if(h?.url){ const a=new Audio(h.url); a.play().catch(()=>toast('Press play in the generated audio card.')); } else toast('Audio is available only in the current session.'); }

  document.addEventListener('DOMContentLoaded', () => { renderPage(); });
})();

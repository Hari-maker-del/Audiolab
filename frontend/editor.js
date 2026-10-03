(() => {
  const API = window.AUDIOLAB_API || '/api';
  const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  let audio = null, sourceFile = null, objectUrl = null, undoStack = [], redoStack = [], trimStart = 0, trimEnd = 0;

  function editorMarkup() {
    return `<div class="editor-shell" id="proEditor">
      <div class="editor-head"><div><div class="eyebrow">Professional Audio Editor</div><h2>Cut, clean and shape your audio</h2><p class="muted">Non-destructive workflow with undo/redo, region selection and one-click processing.</p></div><div class="editor-actions"><label class="btn primary file-btn">Open Audio<input id="editorFile" type="file" accept="audio/*"></label><button class="btn secondary" id="recordEditor">Record</button></div></div>
      <div class="editor-toolbar">
        <button class="tool-btn" data-edit="undo" title="Undo">↶ Undo</button><button class="tool-btn" data-edit="redo" title="Redo">Redo ↷</button><span class="toolbar-sep"></span>
        <button class="tool-btn" data-edit="cut">✂ Cut</button><button class="tool-btn" data-edit="delete">⌫ Delete</button><button class="tool-btn" data-edit="trim">▣ Trim to selection</button><span class="toolbar-sep"></span>
        <button class="tool-btn" data-edit="silence">Remove silence</button><button class="tool-btn" data-edit="normalize">Normalize</button><button class="tool-btn" data-edit="enhance">Enhance voice</button>
      </div>
      <div class="editor-stage">
        <div class="timeline-ruler"><span>0:00</span><span id="rulerEnd">0:00</span></div>
        <canvas id="waveCanvas" height="180"></canvas>
        <div id="selection" class="selection"><span class="sel-left"></span><span class="sel-right"></span></div>
        <div id="playhead" class="playhead"></div>
        <div class="empty-editor" id="editorEmpty"><strong>Drop an audio file here</strong><span>WAV, MP3, FLAC, M4A and browser-supported formats</span></div>
      </div>
      <div class="editor-transport"><button class="transport" id="playEditor">▶</button><button class="transport" id="stopEditor">■</button><span id="editorTime">0:00.000 / 0:00.000</span><input id="zoomEditor" type="range" min="1" max="5" value="1"><span>Zoom</span><span class="selection-readout" id="selectionReadout">Selection: none</span></div>
      <div class="editor-inspector"><div><span>Start</span><input id="startTime" type="number" min="0" step="0.001" value="0"></div><div><span>End</span><input id="endTime" type="number" min="0" step="0.001" value="0"></div><button class="btn secondary" id="applyRange">Apply Range</button><button class="btn primary" id="exportEditor">Export WAV</button></div>
      <div class="editor-status" id="editorStatus">No audio loaded.</div>
    </div>`;
  }

  function install() {
    const page = document.getElementById('page-studio');
    if (!page || page.dataset.editorInstalled === '1') return;
    page.dataset.editorInstalled = '1';
    page.insertAdjacentHTML('beforeend', editorMarkup());
    bind();
  }

  function pushHistory() { if (!sourceFile) return; undoStack.push({start:trimStart,end:trimEnd}); if (undoStack.length > 30) undoStack.shift(); redoStack=[]; }
  function setStatus(text) { const el=document.getElementById('editorStatus'); if(el) el.textContent=text; }
  function format(t){ t=Math.max(0,t); return `${Math.floor(t/60)}:${(t%60).toFixed(3).padStart(6,'0')}`; }

  function draw() {
    const c=document.getElementById('waveCanvas'); if(!c) return; const ctx=c.getContext('2d'); const w=c.clientWidth||900; c.width=w*devicePixelRatio; c.height=180*devicePixelRatio; ctx.scale(devicePixelRatio,devicePixelRatio); ctx.clearRect(0,0,w,180);
    if(!audio || !audio.duration){return;}
    const data = new Float32Array(Math.min(1200, Math.max(200, Math.floor(w))));
    const step = Math.max(1, Math.floor((audio.buffer?.length || 1)/data.length));
    if(audio.buffer){ const ch=audio.buffer.getChannelData(0); for(let i=0;i<data.length;i++){let sum=0;const end=Math.min(ch.length,(i+1)*step);for(let j=i*step;j<end;j++)sum=Math.max(sum,Math.abs(ch[j]));data[i]=sum;} }
    ctx.beginPath(); for(let i=0;i<data.length;i++){const x=i/(data.length-1)*w;const amp=data[i]*70;ctx.moveTo(x,90-amp);ctx.lineTo(x,90+amp);} ctx.lineWidth=1.2; ctx.stroke();
    const left=trimStart/audio.duration*w, right=trimEnd/audio.duration*w; ctx.fillStyle='rgba(0,0,0,.08)';ctx.fillRect(0,0,left,180);ctx.fillRect(right,0,w-right,180);
    document.getElementById('rulerEnd').textContent=format(audio.duration);
  }

  async function loadFile(file){
    sourceFile=file; if(objectUrl)URL.revokeObjectURL(objectUrl); objectUrl=URL.createObjectURL(file);
    const ac=new AudioContext(); const buf=await ac.decodeAudioData(await file.arrayBuffer()); audio={duration:buf.duration,buffer:buf,element:new Audio(objectUrl)}; trimStart=0;trimEnd=buf.duration;undoStack=[];redoStack=[];
    document.getElementById('editorEmpty').style.display='none'; document.getElementById('startTime').value='0'; document.getElementById('endTime').value=buf.duration.toFixed(3); updateSelection(); draw(); setStatus(`${file.name} · ${format(buf.duration)}`);
  }

  function updateSelection(){ if(!audio)return; trimStart=Math.max(0,Math.min(Number(document.getElementById('startTime').value)||0,audio.duration)); trimEnd=Math.max(trimStart,Math.min(Number(document.getElementById('endTime').value)||audio.duration,audio.duration)); const s=document.getElementById('selection'); const l=trimStart/audio.duration*100,r=trimEnd/audio.duration*100;s.style.left=l+'%';s.style.width=(r-l)+'%';document.getElementById('selectionReadout').textContent=`Selection: ${format(trimStart)} → ${format(trimEnd)}`;draw(); }

  function bind(){
    document.getElementById('editorFile').onchange=e=>e.target.files[0]&&loadFile(e.target.files[0]);
    document.getElementById('startTime').oninput=updateSelection; document.getElementById('endTime').oninput=updateSelection; document.getElementById('applyRange').onclick=updateSelection;
    document.getElementById('waveCanvas').onclick=e=>{if(!audio)return;const r=e.currentTarget.getBoundingClientRect();const t=((e.clientX-r.left)/r.width)*audio.duration;document.getElementById('startTime').value=Math.min(t,trimEnd).toFixed(3);updateSelection();};
    document.getElementById('playEditor').onclick=()=>{if(!audio)return;if(audio.element.paused)audio.element.play();else audio.element.pause();};
    document.getElementById('stopEditor').onclick=()=>{if(audio){audio.element.pause();audio.element.currentTime=0;}};
    document.getElementById('exportEditor').onclick=()=>process('trim');
    document.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>edit(b.dataset.edit));
    document.getElementById('recordEditor').onclick=()=>document.querySelector('.nav-item[data-page="voices"]')?.click();
    window.addEventListener('resize',draw);
  }

  async function process(op){
    if(!sourceFile){setStatus('Open an audio file first.');return;}
    pushHistory(); const fd=new FormData();fd.append('file',sourceFile,sourceFile.name);fd.append('start',trimStart);fd.append('end',trimEnd);fd.append('fade_in',0.2);fd.append('fade_out',0.2);fd.append('rate',1);fd.append('semitones',0); setStatus(`Processing: ${op}…`);
    try{const r=await fetch(`${API}/edit/${op}`,{method:'POST',body:fd});if(!r.ok)throw Error(await r.text());const blob=await r.blob();sourceFile=new File([blob],`audiolab-${op}.wav`,{type:'audio/wav'});await loadFile(sourceFile);setStatus(`${op} complete · ready for the next edit.`);}catch(e){setStatus(`Could not process ${op}. Make sure the local backend is running.`);}
  }
  function edit(op){ if(op==='undo'){const h=undoStack.pop();if(h){redoStack.push({start:trimStart,end:trimEnd});trimStart=h.start;trimEnd=h.end;document.getElementById('startTime').value=trimStart;document.getElementById('endTime').value=trimEnd;updateSelection();}}else if(op==='redo'){const h=redoStack.pop();if(h){undoStack.push({start:trimStart,end:trimEnd});trimStart=h.start;trimEnd=h.end;document.getElementById('startTime').value=trimStart;document.getElementById('endTime').value=trimEnd;updateSelection();}}else if(op==='cut'||op==='delete'){process('trim');}else if(op==='trim'||op==='silence'||op==='normalize'||op==='enhance'){process(op);} }

  const observer=new MutationObserver(()=>{if(document.getElementById('page-studio')?.classList.contains('active'))install();});
  observer.observe(document.body,{childList:true,subtree:true});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else setTimeout(install,100);
})();

(() => {
  "use strict";
  const root = document.getElementById("audiolab-pages");
  if (!root) return;
  const DB_NAME = "audiolab-mvp";
  const DB_VERSION = 1;
  const MAX_FILE_BYTES = 100 * 1024 * 1024;
  const AUDIO_EXT = /\.(wav|mp3|m4a|aac|ogg|oga|flac|webm|aiff|aif)$/i;
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
  const prettyBytes = n => n < 1024*1024 ? Math.max(1,Math.round(n/1024))+" KB" : (n/1024/1024).toFixed(1)+" MB";
  const stamp = () => new Date().toISOString();
  const localStatic = () => (location.hostname === "127.0.0.1" || location.hostname === "localhost") && location.port === "5500";
  const routeSearch = () => { const raw=localStatic()&&location.hash.startsWith("#/")?location.hash.slice(1):location.pathname+location.search;return raw.includes("?")?raw.slice(raw.indexOf("?")+1):""; };
  const projectId = () => decodeURIComponent(readPath().split("/")[2] || "");
  const openDB = () => new Promise((resolve,reject) => {
    if (!("indexedDB" in window)) return reject(new Error("This browser does not support local project storage."));
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("projects")) db.createObjectStore("projects",{keyPath:"id"});
      if (!db.objectStoreNames.contains("exports")) db.createObjectStore("exports",{keyPath:"id"});
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("Could not open local project storage."));
  });
  async function store(storeName, mode, action) {
    const db = await openDB();
    return new Promise((resolve,reject) => {
      const tx = db.transaction(storeName,mode);
      const os = tx.objectStore(storeName);
      let result;
      try { result = action(os); } catch (e) { db.close(); reject(e); return; }
      tx.oncomplete = () => { db.close(); resolve(result && result.result !== undefined ? result.result : result); };
      tx.onerror = () => { const e=tx.error; db.close(); reject(e || new Error("Local storage operation failed.")); };
      tx.onabort = () => { const e=tx.error; db.close(); reject(e || new Error("Local storage operation was cancelled.")); };
    });
  }
  const getOne = async (name,key) => { const db=await openDB(); return new Promise((resolve,reject)=>{const tx=db.transaction(name,"readonly");const q=tx.objectStore(name).get(key);q.onsuccess=()=>resolve(q.result||null);q.onerror=()=>reject(q.error);tx.oncomplete=()=>db.close();}); };
  const getAll = async name => { const db=await openDB(); return new Promise((resolve,reject)=>{const tx=db.transaction(name,"readonly");const q=tx.objectStore(name).getAll();q.onsuccess=()=>resolve(q.result||[]);q.onerror=()=>reject(q.error);tx.oncomplete=()=>db.close();}); };
  const put = (name,value) => store(name,"readwrite",os=>os.put(value));
  const del = (name,key) => store(name,"readwrite",os=>os.delete(key));
  const readPath = () => {
    if(localStatic() && location.pathname.endsWith("/app-pages.html")) {
      const hash=location.hash.startsWith("#/")?location.hash.slice(1).split("?")[0]:"/dashboard";
      return hash.replace(/\/+$/,"") || "/";
    }
    return location.pathname.replace(/\/+$/,"") || "/";
  };
  const isEditor = p => /^\/projects\/[^/]+\/editor$/.test(p);
  const isMixer = p => /^\/projects\/[^/]+\/mixer$/.test(p);
  const readFileDuration = file => new Promise(resolve => {
    const url=URL.createObjectURL(file), audio=new Audio();
    audio.preload="metadata";
    audio.onloadedmetadata=()=>{const d=Number.isFinite(audio.duration)?audio.duration:null;URL.revokeObjectURL(url);resolve(d);};
    audio.onerror=()=>{URL.revokeObjectURL(url);resolve(null);};
    audio.src=url;
  });
  function meta(project) {
    return {id:project.id,name:project.name,kind:project.kind,created:project.created,updatedAt:project.updatedAt,hasAudio:!!project.audioBlob,audioName:project.audioName||"",audioType:project.audioType||"",size:project.audioBlob?.size||0,duration:project.duration||null};
  }
  async function syncLegacyIndex() {
    const projects=await getAll("projects");
    localStorage.setItem("audiolab-projects",JSON.stringify(projects.map(meta)));
    return projects;
  }
  function shell(title,group,desc,content) {
    const groups=["Studio","AI tools","Collaboration","Account","Billing","Developer","Admin","System"];
    const navItems={
      "Studio":[["Dashboard","/dashboard"],["Projects","/projects"],["New project","/projects/new"],["Media library","/library"],["Recordings","/recordings"],["Transcript","/transcript"],["Export","/export"],["Export history","/exports"],["Jobs","/jobs"]],
      "AI tools":[["AI cleanup","/ai/cleanup"],["Voice studio","/ai/voice"],["AI music","/ai/music"],["Stem separation","/ai/stems"],["AI mastering","/ai/mastering"]],
      "Collaboration":[["Workspace","/workspace"],["Members","/workspace/members"],["Shared with me","/workspace/shared"],["Review","/review"],["Versions","/versions"],["Notifications","/notifications"]],
      "Account":[["Profile","/account/profile"],["Security","/account/security"],["Integrations","/account/integrations"],["Appearance","/account/appearance"]],
      "Billing":[["Billing","/billing"],["Plans","/billing/plans"],["Usage","/usage"],["Payment methods","/billing/payment-methods"],["Invoices","/billing/invoices"]],
      "Developer":[["API keys","/api-keys"]],
      "Admin":[["Admin overview","/admin"],["Users","/admin/users"],["Workspaces","/admin/workspaces"],["Jobs","/admin/jobs"],["Analytics","/admin/analytics"]],
      "System":[["Status","/status"],["Help","/help"]]
    };
    const nav=groups.map(g=>'<div class="nav-group"><small>'+g+'</small>'+navItems[g].map(x=>'<a class="side-link '+(location.pathname===x[1]?'active':'')+'" href="'+x[1]+'">'+x[0]+'</a>').join("")+'</div>').join("");
    root.innerHTML='<header class="topbar"><a class="brand" href="/"><span class="brand-mark">≈</span><span>Audiolab</span></a><nav><a href="/features">Features</a><a href="/pricing">Pricing</a><a href="/help">Help</a><a class="button" href="/login">Sign in</a><a class="button primary" href="/studio.html">Open Studio</a></nav></header><div class="app-layout"><aside class="sidebar"><a class="brand" href="/dashboard"><span class="brand-mark">≈</span><span>Audiolab</span></a><a class="open-studio" href="/studio.html">♫ &nbsp; Existing local Studio</a><nav>'+nav+'</nav><div class="sidebar-foot"><span class="status-dot"></span> Local-first · projects stay in this browser</div></aside><main class="workspace"><div class="workspace-head"><div><span class="eyebrow">'+esc(group)+'</span><h1>'+esc(title)+'</h1><p class="lead">'+esc(desc)+'</p></div><a class="button primary" href="/projects/new">＋ New project</a></div>'+content+'<footer>Audiolab · Local-first audio workspace <a href="/privacy">Privacy</a><a href="/status">Status</a></footer></main></div>';
  }
  function publicShell(title,group,desc,content) {
    root.innerHTML='<header class="topbar"><a class="brand" href="/"><span class="brand-mark">≈</span><span>Audiolab</span></a><nav><a href="/features">Features</a><a href="/pricing">Pricing</a><a href="/help">Help</a><a class="button" href="/login">Sign in</a><a class="button primary" href="/studio.html">Open Studio</a></nav></header><main class="public-main"><div class="eyebrow">'+esc(group)+' · AUDIO WORKSPACE</div><h1>'+esc(title)+'</h1><p class="lead">'+esc(desc)+'</p>'+content+'</main>';
  }
  function note(message) { const el=document.getElementById("mvp-message"); if(el){el.textContent=message;el.hidden=false;} }
  const messageBox='<p id="mvp-message" class="hint" role="status" aria-live="polite" hidden></p>';
  function projectCard(p) {
    return '<article class="project-card"><span class="project-icon">♫</span><b>'+esc(p.name)+'</b><small>'+esc(p.kind||"Audio editing")+' · '+esc(p.created||"")+'</small>'+(p.audioBlob?'<span class="tag">'+esc(p.audioName||"Audio attached")+' · '+prettyBytes(p.audioBlob.size)+'</span>':'<span class="tag">No audio attached</span>')+'<div class="quick-links"><a href="/projects/'+encodeURIComponent(p.id)+'/editor">Open editor</a><a href="/projects/'+encodeURIComponent(p.id)+'/mixer">Mixer</a></div></article>';
  }
  async function renderProjects() {
    const old=(()=>{try{return JSON.parse(localStorage.getItem("audiolab-projects")||"[]")}catch{return[]}})();
    const all=await syncLegacyIndex();
    const known=new Set(all.map(p=>p.id));
    const list=all.concat(old.filter(p=>!known.has(p.id)).map(p=>({...p,legacy:true})));
    const stats='<div class="stats"><div class="stat"><span>Projects</span><b>'+list.length+'</b><small>Saved in this browser</small></div><div class="stat"><span>Audio files</span><b>'+all.filter(p=>p.audioBlob).length+'</b><small>Stored locally in IndexedDB</small></div><div class="stat"><span>Cloud sync</span><b>Off</b><small>No account required</small></div></div>';
    const content=stats+'<div class="section-head"><div><h2>'+(readPath()==="/dashboard"?"Recent projects":"All projects")+'</h2><p>Project metadata and audio files stay on this browser and device.</p></div><a class="button primary" href="/projects/new">＋ New project</a></div><div class="project-grid">'+(list.length?list.map(projectCard).join(""):'<div class="empty"><div class="project-icon">♫</div><h3>No projects yet</h3><p>Create a project and optionally attach an audio file.</p><a class="button primary" href="/projects/new">Create project</a></div>')+'</div>';
    shell(readPath()==="/dashboard"?"Dashboard":"Projects","Studio","Your local audio workspace and project library.",content);
  }
  async function renderNewProject() {
    const content='<form id="mvp-new-project" class="form-card"><label for="mvp-name">Project name</label><input id="mvp-name" name="name" maxlength="80" required placeholder="e.g. Tamil podcast intro"><label for="mvp-kind">Starting workflow</label><select id="mvp-kind"><option>Audio editing</option><option>Voice generation</option><option>Podcast</option><option>Music and stems</option><option>Dubbing and transcript</option></select><label for="mvp-audio">Audio file (optional)</label><input id="mvp-audio" type="file" accept="audio/*,.wav,.mp3,.m4a,.aac,.ogg,.flac,.webm,.aiff"><p class="hint">Audio is stored locally in this browser. Maximum upload size: 100 MB. No file is uploaded to a cloud server.</p><button class="button primary" type="submit">Create project</button>'+messageBox+'</form>';
    shell("New project","Studio","Create a project and attach audio for local playback and export.",content);
    document.getElementById("mvp-new-project").addEventListener("submit",async e=>{
      e.preventDefault();const button=e.currentTarget.querySelector('button[type="submit"]');button.disabled=true;button.textContent="Saving locally…";
      try{
        const name=document.getElementById("mvp-name").value.trim();const kind=document.getElementById("mvp-kind").value;const file=document.getElementById("mvp-audio").files[0]||null;
        if(file&&file.size>MAX_FILE_BYTES)throw new Error("Choose an audio file smaller than 100 MB.");
        if(file&&!file.type.startsWith("audio/")&&!AUDIO_EXT.test(file.name))throw new Error("Choose a supported audio file.");
        const id=crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+Math.random().toString(36).slice(2,8);
        const project={id,name,kind,created:new Date().toLocaleString(),createdAt:stamp(),updatedAt:stamp(),audioBlob:file,audioName:file?.name||"",audioType:file?.type||"",duration:file?await readFileDuration(file):null,notes:"",editor:{volume:1}};
        await put("projects",project);await syncLegacyIndex();location.href="/projects/"+encodeURIComponent(id)+"/editor";
      }catch(err){button.disabled=false;button.textContent="Create project";note(err.message||"Could not save project locally.");}
    });
  }
  async function renderEditor(mixer=false) {
    const id=projectId();const p=await getOne("projects",id);
    if(!p){shell(mixer?"Mixer":"Project editor","Studio","Open and edit a project stored on this device.",'<div class="notice"><b>Project not found in this browser.</b><p>This project may have been created on another device or in older browser storage.</p><a class="button primary" href="/projects">Back to projects</a></div>');return;}
    if(!Array.isArray(p.tracks))p.tracks=p.audioBlob?[{id:"source-"+p.id,name:p.audioName||"Source audio",audioBlob:p.audioBlob,audioType:p.audioType||"audio/wav",duration:p.duration||0,offset:0,gain:1,muted:false,origin:"source"}]:[];
    const tracks=p.tracks.filter(t=>t&&t.audioBlob);
    const total=Math.max(0,...tracks.map(t=>Math.max(0,Number(t.offset)||0)+Math.max(0,Number(t.duration)||0)));
    const scale=Math.max(10,total);
    const tickCount=Math.min(11,Math.max(3,Math.ceil(scale/5)+1));
    const ticks=Array.from({length:tickCount},(_,i)=>{const time=scale*i/(tickCount-1);return '<span style="left:'+((time/scale)*100)+'%">'+time.toFixed(0)+'s</span>';}).join("");
    const timeline=tracks.length?tracks.map((t,i)=>{
      const offset=Math.max(0,Number(t.offset)||0),duration=Math.max(0,Number(t.duration)||0);
      return '<div class="mvp-track-row"><div class="mvp-track-meta"><b>'+esc(t.name||("Track "+(i+1)))+'</b><small>'+duration.toFixed(2)+'s · '+prettyBytes(t.audioBlob.size||0)+'</small><div class="mvp-track-controls"><label>Start <input type="number" min="0" max="36000" step="0.1" value="'+offset+'" data-track-offset="'+esc(t.id)+'"></label><label>Level <input type="range" min="0" max="1.5" step="0.05" value="'+Math.max(0,Math.min(1.5,Number(t.gain??1)))+'" data-track-gain="'+esc(t.id)+'"></label><label class="mvp-mute"><input type="checkbox" '+(t.muted?'checked':'')+' data-track-mute="'+esc(t.id)+'"> Mute</label><button class="button" type="button" data-track-remove="'+esc(t.id)+'">Remove</button></div></div><div class="mvp-track-lane"><div class="mvp-track-clip" title="'+esc(t.name)+'" style="left:'+Math.min(99,(offset/scale)*100)+'%;width:'+Math.min(100-(offset/scale)*100,Math.max(1,(duration/scale)*100))+'%"><span>♫ '+esc(t.name)+'</span></div></div></div>';
    }).join(""):'<div class="empty compact"><h3>No tracks yet</h3><p>Add an audio file or save generated speech from Studio into this project.</p></div>';
    const content='<div class="editor-placeholder"><div class="editor-toolbar"><a class="button" href="/projects">← Projects</a><span class="tag">'+esc(p.kind||"Audio editing")+'</span><a class="button primary" href="/export?project='+encodeURIComponent(id)+'">Export / Mixdown</a></div><section class="mvp-timeline-card"><div class="mvp-timeline-heading"><div><h2>Timeline</h2><p class="hint">Tracks are stored in this browser. Set each start time, level and mute state, then save.</p></div><div class="quick-links"><button class="button primary" id="mvp-timeline-play" type="button">▶ Play mix</button><button class="button" id="mvp-timeline-stop" type="button">■ Stop</button><label class="button" for="mvp-add-track">＋ Add track</label><input id="mvp-add-track" type="file" accept="audio/*,.wav,.mp3,.m4a,.aac,.ogg,.flac,.webm,.aiff" multiple hidden><label class="button" for="mvp-replace-source">Replace primary audio</label><input id="mvp-replace-source" type="file" accept="audio/*,.wav,.mp3,.m4a,.aac,.ogg,.flac,.webm,.aiff" hidden></div></div><div class="mvp-timeline-ruler">'+ticks+'</div><div class="mvp-timeline-tracks">'+timeline+'</div><p id="mvp-timeline-status" class="hint" role="status" aria-live="polite">Timeline length: '+total.toFixed(2)+' seconds · '+tracks.length+' track(s)</p></section><form id="mvp-project-form" class="form-card" style="margin-top:18px"><label for="mvp-editor-name">Project name</label><input id="mvp-editor-name" maxlength="80" required value="'+esc(p.name)+'"><label for="mvp-notes">Project notes / script</label><textarea id="mvp-notes" rows="4" placeholder="Add edit notes, script or export reminders…">'+esc(p.notes||"")+'</textarea>'+(mixer?'<label for="mvp-volume">Master preview volume</label><input id="mvp-volume" type="range" min="0" max="1" step="0.05" value="'+Number(p.editor?.volume??1)+'">':'')+'<div class="quick-links"><button class="button primary" type="submit">Save project and timeline</button><button class="button" id="mvp-delete-project" type="button">Delete project</button></div>'+messageBox+'</form></div>';
    shell(mixer?"Mixer":"Project editor","Studio",mixer?"Preview your audio timeline and adjust local playback level.":"Arrange generated voice and imported audio as persistent local tracks.",content);
    const status=document.getElementById("mvp-timeline-status");
    const form=document.getElementById("mvp-project-form");
    let timelineContext=null,timelineNodes=[],stopTimer=null;
    const stopMix=async()=>{if(stopTimer)clearTimeout(stopTimer);stopTimer=null;timelineNodes.forEach(node=>{try{node.stop();}catch(_){}});timelineNodes=[];if(timelineContext){const ctx=timelineContext;timelineContext=null;await ctx.close().catch(()=>{});}if(status)status.textContent="Playback stopped.";};
    document.getElementById("mvp-timeline-stop").addEventListener("click",stopMix);
    document.getElementById("mvp-timeline-play").addEventListener("click",async()=>{
      await stopMix();
      const active=p.tracks.filter(t=>t&&t.audioBlob);
      if(!active.length){if(status)status.textContent="Add at least one audio track first.";return;}
      const Ctx=window.AudioContext||window.webkitAudioContext;
      if(!Ctx){if(status)status.textContent="Audio playback is not supported by this browser.";return;}
      const button=document.getElementById("mvp-timeline-play");button.disabled=true;
      try{
        const ctx=new Ctx();timelineContext=ctx;await ctx.resume();
        const decodedTracks=[];
        for(const track of active)decodedTracks.push({track,buffer:await ctx.decodeAudioData(await track.audioBlob.arrayBuffer())});
        const startAt=ctx.currentTime+0.12;let maxEnd=0;
        const masterVolume=mixer?Number(document.getElementById("mvp-volume")?.value??1):1;
        for(const item of decodedTracks){
          const track=item.track,decoded=item.buffer;
          const source=ctx.createBufferSource();source.buffer=decoded;
          const gain=ctx.createGain();gain.gain.value=track.muted?0:Math.max(0,Math.min(1.5,Number(track.gain??1)))*Math.max(0,Math.min(1,masterVolume));
          source.connect(gain);gain.connect(ctx.destination);
          const offset=Math.max(0,Number(track.offset)||0);source.start(startAt+offset);
          timelineNodes.push(source);maxEnd=Math.max(maxEnd,offset+decoded.duration);
        }

        if(status)status.textContent="Playing "+active.length+" track(s)…";
        stopTimer=setTimeout(()=>{stopMix();},Math.max(0,maxEnd*1000+250));
      }catch(error){await stopMix();if(status)status.textContent="Could not play the timeline: "+(error.message||"audio decode failed");}
      finally{button.disabled=false;}
    });
    const replaceSource=document.getElementById("mvp-replace-source");
    replaceSource.addEventListener("change",async()=>{
      const file=replaceSource.files?.[0];if(!file)return;
      if(file.size>MAX_FILE_BYTES){if(status)status.textContent="Choose a file smaller than 100 MB.";return;}
      if(!file.type.startsWith("audio/")&&!AUDIO_EXT.test(file.name)){if(status)status.textContent="Choose a supported audio file.";return;}
      try{
        const duration=await readFileDuration(file);
        p.audioBlob=file;p.audioName=file.name;p.audioType=file.type;p.duration=duration;
        let primary=p.tracks.find(t=>t.id===p.activeTrackId)||p.tracks[0];
        if(primary){primary.name=file.name;primary.audioBlob=file;primary.audioType=file.type;primary.duration=duration;primary.offset=0;primary.gain=1;primary.muted=false;}
        else{primary={id:crypto.randomUUID?crypto.randomUUID():Date.now().toString(36),name:file.name,audioBlob:file,audioType:file.type,duration,offset:0,gain:1,muted:false,origin:"source"};p.tracks.push(primary);}
        p.activeTrackId=primary.id;p.updatedAt=stamp();await put("projects",p);await syncLegacyIndex();location.reload();
      }catch(error){if(status)status.textContent=error.message||"Could not replace primary audio.";}
    });
    const addInput=document.getElementById("mvp-add-track");
    addInput.addEventListener("change",async()=>{
      const files=[...(addInput.files||[])];if(!files.length)return;
      try{
        for(const file of files){
          if(file.size>MAX_FILE_BYTES)throw new Error(file.name+" exceeds the 100 MB file limit.");
          if(!file.type.startsWith("audio/")&&!AUDIO_EXT.test(file.name))throw new Error("Choose a supported audio file.");
          if(window.AudiolabProjectAssets?.addTrack)await window.AudiolabProjectAssets.addTrack(p.id,file,{origin:"imported"});
          else {const duration=await readFileDuration(file);p.tracks.push({id:crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+Math.random().toString(36).slice(2,6),name:file.name,audioBlob:file,audioType:file.type,duration,offset:0,gain:1,muted:false,origin:"imported"});await put("projects",p);}
        }
        location.reload();
      }catch(error){if(status)status.textContent=error.message||"Could not add the audio track.";}
    });
    document.querySelectorAll("[data-track-offset]").forEach(input=>input.addEventListener("change",async()=>{
      const track=p.tracks.find(t=>t.id===input.dataset.trackOffset);if(!track)return;
      track.offset=Math.max(0,Number(input.value)||0);p.updatedAt=stamp();await put("projects",p);if(status)status.textContent="Track start saved.";
    }));
    document.querySelectorAll("[data-track-gain]").forEach(input=>input.addEventListener("input",()=>{
      const track=p.tracks.find(t=>t.id===input.dataset.trackGain);if(track)track.gain=Math.max(0,Math.min(1.5,Number(input.value)||0));
    }));
    document.querySelectorAll("[data-track-gain]").forEach(input=>input.addEventListener("change",async()=>{p.updatedAt=stamp();await put("projects",p);if(status)status.textContent="Track level saved."; }));
    document.querySelectorAll("[data-track-mute]").forEach(input=>input.addEventListener("change",async()=>{
      const track=p.tracks.find(t=>t.id===input.dataset.trackMute);if(!track)return;track.muted=input.checked;p.updatedAt=stamp();await put("projects",p);if(status)status.textContent=track.muted?"Track muted.":"Track unmuted.";
    }));
    document.querySelectorAll("[data-track-remove]").forEach(button=>button.addEventListener("click",async()=>{
      const track=p.tracks.find(t=>t.id===button.dataset.trackRemove);if(!track)return;
      if(!confirm("Remove "+(track.name||"this track")+" from the timeline?"))return;
      await stopMix();p.tracks=p.tracks.filter(t=>t.id!==track.id);p.updatedAt=stamp();await put("projects",p);location.reload();
    }));
    form.addEventListener("submit",async e=>{
      e.preventDefault();p.name=document.getElementById("mvp-editor-name").value.trim();p.notes=document.getElementById("mvp-notes").value;p.updatedAt=stamp();
      if(mixer){p.editor=p.editor||{};p.editor.volume=Number(document.getElementById("mvp-volume").value);}
      await put("projects",p);await syncLegacyIndex();note("Project and timeline saved in this browser.");
    });
    document.getElementById("mvp-delete-project").addEventListener("click",async()=>{
      if(!confirm("Delete this project and its locally stored audio tracks? This cannot be undone."))return;
      await stopMix();await del("projects",p.id);await syncLegacyIndex();location.href="/projects";
    });
  }
  function makeWav(audioBuffer) {
    const channels=audioBuffer.numberOfChannels,sampleRate=audioBuffer.sampleRate,frames=audioBuffer.length;
    const bytesPerSample=2,dataSize=frames*channels*bytesPerSample;
    const out=new ArrayBuffer(44+dataSize),view=new DataView(out);
    const write=(offset,s)=>{for(let i=0;i<s.length;i++)view.setUint8(offset+i,s.charCodeAt(i));};
    write(0,"RIFF");view.setUint32(4,36+dataSize,true);write(8,"WAVE");write(12,"fmt ");view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,channels,true);view.setUint32(24,sampleRate,true);view.setUint32(28,sampleRate*channels*bytesPerSample,true);view.setUint16(32,channels*bytesPerSample,true);view.setUint16(34,16,true);write(36,"data");view.setUint32(40,dataSize,true);
    const channelData=Array.from({length:channels},(_,i)=>audioBuffer.getChannelData(i));let offset=44;
    for(let i=0;i<frames;i++)for(let c=0;c<channels;c++){const s=Math.max(-1,Math.min(1,channelData[c][i]));view.setInt16(offset,s<0?s*0x8000:s*0x7fff,true);offset+=2;}
    return new Blob([out],{type:"audio/wav"});
  }
  function downloadBlob(blob,name) {
    const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);
  }
  async function renderTimelineMix(project) {
    const tracks=Array.isArray(project.tracks)?project.tracks.filter(t=>t&&t.audioBlob):[];
    if(!tracks.length&&project.audioBlob)tracks.push({id:"source-"+project.id,name:project.audioName||"Source audio",audioBlob:project.audioBlob,offset:0,gain:1,muted:false});
    if(!tracks.length)throw new Error("Add at least one audio track before exporting a mixdown.");
    const Ctx=window.AudioContext||window.webkitAudioContext;
    const Offline=window.OfflineAudioContext||window.webkitOfflineAudioContext;
    if(!Ctx||!Offline)throw new Error("Timeline mixdown is not supported by this browser.");
    const decoder=new Ctx();
    try{
      const decoded=[];
      for(const track of tracks)decoded.push({track,buffer:await decoder.decodeAudioData(await track.audioBlob.arrayBuffer())});
      const duration=Math.max(...decoded.map(x=>Math.max(0,Number(x.track.offset)||0)+x.buffer.duration));
      if(!Number.isFinite(duration)||duration<=0)throw new Error("The timeline has no playable duration.");
      const sampleRate=44100;
      const offline=new Offline(2,Math.ceil(duration*sampleRate),sampleRate);
      for(const item of decoded){
        const source=offline.createBufferSource();source.buffer=item.buffer;
        const gain=offline.createGain();
        gain.gain.value=item.track.muted?0:Math.max(0,Math.min(1.5,Number(item.track.gain??1)));
        source.connect(gain);gain.connect(offline.destination);
        source.start(Math.max(0,Number(item.track.offset)||0));
      }
      return makeWav(await offline.startRendering());
    }finally{await decoder.close().catch(()=>{});}
  }
  async function exportProject(project,format) {
    if(format!=="mixdown"&&!project.audioBlob)throw new Error("This project has no original audio file. Add a track first.");
    let blob=project.audioBlob,extension=(project.audioName.match(/\.([^.]+)$/)||[])[1]||"audio";
    if(format==="mixdown"){blob=await renderTimelineMix(project);extension="wav";}
    if(format==="wav"){
      const Ctx=window.AudioContext||window.webkitAudioContext;if(!Ctx)throw new Error("WAV conversion is not supported by this browser.");
      const ctx=new Ctx();
      try{const buffer=await project.audioBlob.arrayBuffer();const decoded=await ctx.decodeAudioData(buffer);blob=makeWav(decoded);extension="wav";}
      catch(e){throw new Error("Your browser could not decode this audio for WAV export. Try the original-file export instead.");}
      finally{await ctx.close().catch(()=>{});}
    }
    const safe=(project.name||"audiolab-project").replace(/[^a-z0-9_-]+/gi,"-").replace(/^-|-$/g,"")||"audiolab-project";
    const name=safe+"."+extension;downloadBlob(blob,name);
    const entry={id:Date.now().toString(36)+Math.random().toString(36).slice(2,7),projectId:project.id,projectName:project.name,fileName:name,format:format==="wav"?"WAV":format==="mixdown"?"Timeline mixdown":"Original",size:blob.size,createdAt:stamp(),blob};
    await put("exports",entry);
    return entry;
  }
  async function renderExport() {
    const all=await getAll("projects");const params=new URLSearchParams(routeSearch());const chosen=params.get("project")||all[0]?.id;
    const options=all.map(p=>'<option value="'+esc(p.id)+'" '+(p.id===chosen?'selected':'')+'>'+esc(p.name)+(p.audioBlob?'':' (no audio')+'</option>').join("");
    const content='<form id="mvp-export-form" class="form-card"><label for="mvp-export-project">Project</label><select id="mvp-export-project">'+(options||'<option value="">No projects available</option>')+'</select><label>Export format</label><div class="quick-links"><label><input type="radio" name="format" value="original" checked> Original audio</label><label><input type="radio" name="format" value="wav"> Convert original to WAV (PCM 16-bit)</label><label><input type="radio" name="format" value="mixdown"> Render timeline mixdown (WAV)</label></div><p class="hint">Exports run locally in your browser. Timeline mixdown combines saved tracks, start offsets, levels and mute settings into a WAV file.</p><button class="button primary" type="submit">Export and download</button>'+messageBox+'</form><div class="quick-links"><a href="/exports">View export history</a><a href="/projects">Back to projects</a></div>';
    shell("Export audio","Studio","Download an original audio file or convert supported audio to WAV locally.",content);
    document.getElementById("mvp-export-form").addEventListener("submit",async e=>{e.preventDefault();const btn=e.currentTarget.querySelector('button[type="submit"]');btn.disabled=true;btn.textContent="Preparing export…";try{const id=document.getElementById("mvp-export-project").value;const p=await getOne("projects",id);if(!p)throw new Error("Choose an existing project.");const format=new FormData(e.currentTarget).get("format")||"original";const result=await exportProject(p,format);note("Downloaded "+result.fileName+" and saved it to local export history.");}catch(err){note(err.message||"Export failed.");}finally{btn.disabled=false;btn.textContent="Export and download";}});
  }
  async function renderExports() {
    const items=(await getAll("exports")).sort((a,b)=>b.createdAt.localeCompare(a.createdAt));
    const content=items.length?'<div class="project-grid">'+items.map(x=>'<article class="project-card"><span class="project-icon">⇩</span><b>'+esc(x.fileName)+'</b><small>'+esc(x.projectName)+' · '+new Date(x.createdAt).toLocaleString()+'</small><span class="tag">'+esc(x.format)+' · '+prettyBytes(x.size)+'</span><div class="quick-links"><button class="button" data-redownload="'+esc(x.id)+'">Download again</button><button class="button" data-remove-export="'+esc(x.id)+'">Remove</button></div></article>').join("")+'</div>':'<div class="empty"><h3>No exports yet</h3><p>Export audio from a project and it will appear here.</p><a class="button primary" href="/export">Export audio</a></div>';
    shell("Export history","Studio","Files exported in this browser are retained locally for future downloads.",content);
    root.querySelectorAll("[data-redownload]").forEach(b=>b.addEventListener("click",async()=>{const item=await getOne("exports",b.dataset.redownload);if(item?.blob)downloadBlob(item.blob,item.fileName);else alert("This export no longer has a stored file.");}));
    root.querySelectorAll("[data-remove-export]").forEach(b=>b.addEventListener("click",async()=>{await del("exports",b.dataset.removeExport);renderExports();}));
  }
  async function renderJobs() {
    const exports=await getAll("exports");const content='<div class="notice"><b>Local processing status</b><p>This page lists exports created by this browser. It does not invent server-side jobs. For actual AI generation and transcription, open the local Studio and ensure the FastAPI backend and model are ready.</p><a class="button primary" href="/studio.html">Open local Studio</a></div>'+(exports.length?'<div class="project-grid">'+exports.sort((a,b)=>b.createdAt.localeCompare(a.createdAt)).map(x=>'<article class="project-card"><b>'+esc(x.projectName)+'</b><span class="tag">Export saved</span><small>'+esc(x.fileName)+' · '+new Date(x.createdAt).toLocaleString()+'</small></article>').join("")+'</div>':'<div class="empty"><h3>No local exports or jobs</h3><p>Your export history will appear here after you export a project.</p></div>');
    shell("Jobs","Studio","Local export history and a safe handoff to actual AI processing.",content);
  }
  async function renderSettings() {
    let prefs={};try{prefs=JSON.parse(localStorage.getItem("audiolab-preferences")||"{}")}catch{}
    const content='<form id="mvp-settings" class="form-card"><label for="mvp-language">Preferred language</label><select id="mvp-language">'+["Tamil","English","Telugu","Malayalam","Hindi","Kannada","Bengali","Gujarati","Marathi","Odia","Punjabi","Assamese"].map(x=>'<option '+((prefs.language||"Tamil")===x?'selected':'')+'>'+x+'</option>').join("")+'</select><label for="mvp-workflow">Default workflow</label><select id="mvp-workflow">'+["Voice and narration","Audio editing","Podcast editing","Music and stems","Dubbing and transcripts"].map(x=>'<option '+((prefs.workflow||"Voice and narration")===x?'selected':'')+'>'+x+'</option>').join("")+'</select><label for="mvp-theme">Appearance</label><select id="mvp-theme"><option value="dark">Turmeric × Malt (dark)</option><option value="system">Use browser preference (planned)</option></select><button class="button primary">Save preferences</button>'+messageBox+'</form><div class="notice"><b>Local preferences</b><p>These settings are stored in this browser. Account-wide sync and cloud integrations are not connected.</p></div>';
    shell("Settings","Account","Choose your preferred language and workflow for this browser.",content);
    document.getElementById("mvp-settings").addEventListener("submit",e=>{e.preventDefault();localStorage.setItem("audiolab-preferences",JSON.stringify({language:document.getElementById("mvp-language").value,workflow:document.getElementById("mvp-workflow").value,theme:document.getElementById("mvp-theme").value}));note("Preferences saved in this browser.");});
  }
  async function renderAI(path) {
    const map={"/ai/cleanup":["AI cleanup","Prepare an audio cleanup workflow."],"/ai/voice":["Voice studio","Generate speech using an authorized reference voice."],"/ai/music":["AI music","Check available local audio tools and model readiness."],"/ai/stems":["Stem separation","Stem separation depends on a supported local model."],"/ai/mastering":["AI mastering","Prepare an audio mastering workflow."]};
    const x=map[path]||map["/ai/voice"];
    shell(x[0],"AI tools",x[1],'<div class="tool-grid"><article class="tool-card"><span class="feature-icon">♫</span><h3>Open the existing Studio</h3><p>Use the established local audio workspace and its actual backend integrations.</p><a class="button primary" href="/studio.html">Open Studio</a></article><article class="tool-card"><span class="feature-icon">⌁</span><h3>Check local backend</h3><p>The Windows FastAPI service should remain local at 127.0.0.1:8000. It is not exposed publicly.</p><button class="button" id="mvp-health">Check local API</button><p id="mvp-health-result" class="hint" role="status"></p></article></div><div class="notice"><b>No fake inference.</b><p>This page only reports model work as available when the existing backend actually confirms it. Open Studio to use currently implemented tools.</p></div>');
    document.getElementById("mvp-health").addEventListener("click",async()=>{const out=document.getElementById("mvp-health-result");out.textContent="Checking…";try{const r=await fetch("http://127.0.0.1:8000/health",{signal:AbortSignal.timeout(3000)});if(!r.ok)throw Error("API returned "+r.status);const data=await r.json();out.textContent="Local API reachable"+(data.status?": "+data.status:"")+". Check Models in Studio for model readiness.";}catch(e){out.textContent="Local API is not reachable from this browser. Start Audiolab on your Windows computer."; }});
  }
  async function renderBilling(path) {
    const title=path==="/billing/plans"?"Plans":path==="/usage"?"Usage and credits":"Billing";
    const content='<div class="plan-grid"><article class="plan"><span class="tag">Available now</span><h2>Free / Local</h2><p>Run supported audio models on your own computer.</p><ul><li>No subscription required for local workflows</li><li>Local files and browser storage</li><li>Performance depends on your hardware</li></ul><a class="button primary" href="/studio.html">Open Studio</a></article><article class="plan"><span class="tag">Not connected</span><h2>Cloud features</h2><p>Account-based usage, online storage and payments are not enabled.</p><ul><li>No card is charged by this page</li><li>No paid plan is simulated</li><li>Billing provider integration required</li></ul><a class="button" href="/help">Setup help</a></article></div>';
    shell(title,"Billing","Transparent plan status: this MVP does not accept payments or claim cloud credits.",content);
  }
  async function renderAuth(path) {
    const titles={"/signup":"Create account","/login":"Sign in","/forgot-password":"Forgot password","/reset-password":"Reset password","/verify":"Verify email","/auth/callback":"Authentication callback","/onboarding":"Welcome setup","/onboarding/invite":"Accept invitation"};
    if(path==="/onboarding"){await renderSettings();return;}
    const title=titles[path]||"Authentication";
    publicShell(title,"Account","Authentication is not connected yet.",'<div class="form-card"><div class="notice"><b>No account actions are simulated.</b><p>Connect a real authentication provider before enabling registration, password resets, email verification or invitations.</p></div><p><a class="button primary" href="/studio.html">Continue with local Studio</a></p><div class="quick-links"><a href="/signup">Sign up</a><a href="/login">Login</a><a href="/forgot-password">Forgot password</a></div></div>');
  }
  async function render() {
    const p=readPath();
    try{
      if(p==="/dashboard"||p==="/projects"){await renderProjects();return;}
      if(p==="/projects/new"){await renderNewProject();return;}
      if(isEditor(p)){await renderEditor(false);return;}
      if(isMixer(p)){await renderEditor(true);return;}
      if(p==="/export"){await renderExport();return;}
      if(p==="/exports"){await renderExports();return;}
      if(p==="/jobs"){await renderJobs();return;}
      if(p==="/account/appearance"||p==="/account/profile"){await renderSettings();return;}
      if(p==="/billing"||p==="/billing/plans"||p==="/usage"||p==="/billing/payment-methods"||p==="/billing/invoices"){await renderBilling(p);return;}
      if(p.startsWith("/ai/")){await renderAI(p);return;}
      if(["/signup","/login","/forgot-password","/reset-password","/verify","/auth/callback","/onboarding","/onboarding/invite"].includes(p)){await renderAuth(p);return;}
      if(p==="/"){return;}
      if(p==="/api-keys"||p==="/account/delete"||p.startsWith("/admin")){shell(p.startsWith("/admin")?"Admin area":p==="/api-keys"?"API keys":"Delete account","Restricted", "This route is reserved for a secure integration.",'<div class="notice"><b>Not enabled.</b><p>Authentication, role-based access and server-side authorization are required before this route can expose data or perform sensitive actions.</p></div>');return;}
    }catch(error){
      root.innerHTML='<main class="public-main"><h1>Could not load this page</h1><p class="lead">'+esc(error.message||"Local storage error")+'</p><a class="button primary" href="/projects">Back to projects</a></main>';
    }
  }
  if(localStatic()) {
    document.addEventListener("click",event=>{
      const link=event.target.closest("a[href]");
      if(!link||event.defaultPrevented||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
      const url=new URL(link.href,location.href);
      if(url.origin!==location.origin||url.pathname.endsWith(".html")||url.pathname.startsWith("/api/"))return;
      if(!url.pathname.startsWith("/"))return;
      event.preventDefault();
      location.hash=url.pathname+url.search;
    });
    window.addEventListener("hashchange",render);
  }
  render();
})();
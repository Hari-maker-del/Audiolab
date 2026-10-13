(() => {
  "use strict";
  const DB = "audiolab-voice-conversion";
  const STORE = "target-voices";
  let sourceFile = null, targetFile = null, selectedVoiceId = "", outputFile = null, outputUrl = null, busy = false, previewUrls = [];

  const esc = v => String(v == null ? "" : v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const toast = msg => {
    const el = document.getElementById("toast");
    if (el) { el.textContent = msg; el.classList.add("show"); setTimeout(() => el.classList.remove("show"), 2800); }
    else console.info(msg);
  };
  const apiBase = () => window.AUDIOLAB_LOCAL_API || (["localhost","127.0.0.1"].includes(location.hostname) ? "http://127.0.0.1:8000" : "");
  const uid = () => crypto && crypto.randomUUID ? crypto.randomUUID() : ("voice-" + Date.now() + "-" + Math.random().toString(16).slice(2));

  function dbOpen() {
    return new Promise((resolve, reject) => {
      if (!indexedDB) return reject(new Error("This browser does not support local voice storage."));
      const r = indexedDB.open(DB, 1);
      r.onupgradeneeded = () => { if (!r.result.objectStoreNames.contains(STORE)) r.result.createObjectStore(STORE, {keyPath:"id"}); };
      r.onsuccess = () => resolve(r.result);
      r.onerror = () => reject(r.error || new Error("Could not open local voice storage."));
    });
  }
  async function allVoices() {
    const d = await dbOpen();
    try { return await new Promise((resolve,reject) => {
      const t = d.transaction(STORE,"readonly"), r = t.objectStore(STORE).getAll();
      r.onsuccess = () => resolve((r.result || []).sort((a,b) => b.createdAt-a.createdAt));
      r.onerror = () => reject(r.error || new Error("Could not load saved voices."));
    }); } finally { d.close(); }
  }
  async function getVoice(id) {
    const d = await dbOpen();
    try { return await new Promise((resolve,reject) => {
      const r=d.transaction(STORE,"readonly").objectStore(STORE).get(id);
      r.onsuccess=()=>resolve(r.result||null); r.onerror=()=>reject(r.error);
    }); } finally { d.close(); }
  }
  async function saveVoice(file,name) {
    if (!file) throw new Error("Choose a target reference audio first.");
    const entry = {id:uid(),name:(String(name||"").trim()||file.name||"Target voice").slice(0,80),fileName:file.name||"target-voice.wav",type:file.type||"audio/wav",size:file.size||0,createdAt:Date.now(),blob:file};
    const d=await dbOpen();
    try { await new Promise((resolve,reject)=>{const t=d.transaction(STORE,"readwrite");t.objectStore(STORE).put(entry);t.oncomplete=resolve;t.onerror=()=>reject(t.error||new Error("Could not save voice."));}); }
    finally { d.close(); }
    return entry;
  }
  async function changeVoice(id,action,value) {
    const d=await dbOpen();
    try { await new Promise((resolve,reject)=>{
      const t=d.transaction(STORE,"readwrite"),s=t.objectStore(STORE);
      if(action==="delete"){s.delete(id);}
      else {const r=s.get(id);r.onsuccess=()=>{if(r.result){r.result.name=String(value||r.result.name).trim().slice(0,80);s.put(r.result);}};r.onerror=()=>reject(r.error);}
      t.oncomplete=resolve;t.onerror=()=>reject(t.error||new Error("Could not update saved voice."));
    }); } finally {d.close();}
    if(selectedVoiceId===id && action==="delete") selectedVoiceId="";
  }
  const asFile = v => v && v.blob ? new File([v.blob],v.fileName||"target-voice.wav",{type:v.type||v.blob.type||"audio/wav"}) : null;

  function mountStudio() {
    const page=document.getElementById("page-studio");
    if(!page || page.querySelector("#voiceConvertDashboard")) return;
    const card=document.createElement("section"); card.id="voiceConvertDashboard"; card.className="card"; card.style.marginTop="18px";
    card.innerHTML = '<div class="eyebrow">AI Voice Convert</div><h3 style="margin-top:9px">Keep your performance. Change the vocal timbre.</h3>' +
      '<p class="muted">Upload your recorded dialogue and a separate target-voice reference. This calls a local AI audio-to-audio conversion model, not text-to-speech. Timing, pitch, and emotion can still change.</p>' +
      '<div class="vc-layout"><div class="vc-field"><label for="vc-source">1 · Your original voice-over</label><input id="vc-source" type="file" accept="audio/*"><div id="vc-source-info" class="vc-help">Choose your original recording.</div></div>' +
      '<div class="vc-field"><label for="vc-target">2 · Target reference voice</label><input id="vc-target" type="file" accept="audio/*"><div id="vc-target-info" class="vc-help">Choose a voice you own or have permission to use.</div></div>' +
      '<div class="vc-field"><label for="vc-saved-target">Or choose a saved target voice</label><select id="vc-saved-target" class="select"><option value="">Loading saved voices…</option></select><div class="vc-help">Saved in this browser on this device.</div></div>' +
      '<div class="vc-field"><label for="vc-target-name">Name this reference (optional)</label><input id="vc-target-name" type="text" maxlength="80" placeholder="e.g. Raspy comic style"><button id="vc-save-target" class="btn secondary" type="button">Save target reference to Voices</button></div></div>' +
      '<div class="vc-consent" style="margin-top:17px"><input id="vc-consent" type="checkbox"><label for="vc-consent">I own or have permission to use both recordings and will not use the result for deceptive impersonation.</label></div>' +
      '<div class="actions" style="margin-top:16px;align-items:center"><button id="vc-convert" class="btn primary" type="button">Convert Voice</button><span id="vc-backend-state" class="vc-model-state">Checking local model…</span></div>' +
      '<p class="vc-note">Processing stays on your PC when using the local backend. Model weights must be installed separately; CPU inference may be slow.</p><div id="vc-result"></div>';
    page.appendChild(card);

    const src=card.querySelector("#vc-source"), tgt=card.querySelector("#vc-target"), select=card.querySelector("#vc-saved-target");
    src.addEventListener("change",()=>{sourceFile=src.files&&src.files[0]||null;card.querySelector("#vc-source-info").textContent=sourceFile?sourceFile.name+" · "+(sourceFile.size/1048576).toFixed(2)+" MB":"No source selected.";});
    tgt.addEventListener("change",()=>{targetFile=tgt.files&&tgt.files[0]||null;selectedVoiceId="";select.value="";card.querySelector("#vc-target-info").textContent=targetFile?targetFile.name+" · "+(targetFile.size/1048576).toFixed(2)+" MB":"No target reference selected.";});
    select.addEventListener("change",async()=>{selectedVoiceId=select.value;targetFile=null;tgt.value="";const v=selectedVoiceId?await getVoice(selectedVoiceId):null;card.querySelector("#vc-target-info").textContent=v?"Saved reference: "+v.name+" ("+v.fileName+")":"Choose a target audio file.";});
    card.querySelector("#vc-save-target").addEventListener("click",async()=>{
      if(!targetFile) return toast("Choose a new target audio file before saving it.");
      try {const v=await saveVoice(targetFile,card.querySelector("#vc-target-name").value);selectedVoiceId=v.id;targetFile=null;tgt.value="";await fillTargetSelect(card);card.querySelector("#vc-saved-target").value=v.id;card.querySelector("#vc-target-info").textContent="Saved reference: "+v.name;await refreshLibrary();toast("Target voice saved locally.");}
      catch(e){toast(e.message||"Could not save target voice.");}
    });
    card.querySelector("#vc-convert").addEventListener("click",()=>convert(card));
    fillTargetSelect(card); modelStatus(card); renderOutput(card);
  }
  async function fillTargetSelect(card) {
    const sel=card.querySelector("#vc-saved-target"); if(!sel)return;
    try {const voices=await allVoices();sel.innerHTML='<option value="">Choose a saved target voice…</option>'+voices.map(v=>'<option value="'+esc(v.id)+'">'+esc(v.name)+' · '+esc(v.fileName)+'</option>').join("");if(selectedVoiceId && voices.some(v=>v.id===selectedVoiceId))sel.value=selectedVoiceId;}
    catch(e){sel.innerHTML='<option value="">Local voice storage unavailable</option>';toast(e.message||"Could not load voices.");}
  }
  async function convert(card) {
    if(busy)return;
    if(!sourceFile)return toast("Choose your original voice-over first.");
    let actualTarget=targetFile;
    if(selectedVoiceId){try{actualTarget=asFile(await getVoice(selectedVoiceId));}catch(e){return toast(e.message||"Could not load saved target voice.");}}
    if(!actualTarget)return toast("Upload a target reference or select a saved voice.");
    if(!card.querySelector("#vc-consent").checked)return toast("Confirm permission to use both recordings first.");
    const base=apiBase();if(!base)return toast("Voice conversion requires the local backend. Run START-AUDIOLAB.bat on your Windows PC.");
    const button=card.querySelector("#vc-convert"),result=card.querySelector("#vc-result");
    busy=true;button.disabled=true;button.textContent="Converting…";
    result.innerHTML='<div class="vc-result"><strong>Running real AI voice conversion…</strong><p class="vc-help">The local backend is processing both recordings. Keep the app open.</p></div>';
    const form=new FormData();form.append("source_file",sourceFile,sourceFile.name||"source.wav");form.append("target_file",actualTarget,actualTarget.name||"target.wav");form.append("consent","true");
    try {
      const response=await fetch(base+"/voice-convert",{method:"POST",body:form});
      if(!response.ok){let message="";try{const body=await response.json();message=body.detail||JSON.stringify(body);}catch(_){message=await response.text();}throw new Error(message||("Backend returned HTTP "+response.status));}
      const blob=await response.blob();if(!blob||blob.size<=44)throw new Error("Backend returned an empty or invalid audio file.");
      if(outputUrl)URL.revokeObjectURL(outputUrl);outputFile=new File([blob],"audiolab-voice-converted.wav",{type:"audio/wav"});outputUrl=URL.createObjectURL(outputFile);
      renderOutput(card);toast("AI conversion finished. Compare the output with your original performance.");modelStatus(card);
    } catch(e) {
      result.innerHTML='<div class="vc-result"><strong>Conversion did not complete</strong><p class="vc-help">'+esc(e.message||e)+'</p><p class="vc-note">No converted audio is shown unless the backend returns a real file.</p></div>';toast("Voice conversion failed. See the Studio error message.");modelStatus(card);
    } finally {busy=false;button.disabled=false;button.textContent="Convert Voice";}
  }
  function renderOutput(card) {
    const result=card.querySelector("#vc-result");if(!result)return;
    if(!outputFile||!outputUrl){result.innerHTML="";return;}
    result.innerHTML='<div class="vc-result"><div class="eyebrow">AI-CONVERTED AUDIO</div><h3 style="margin-top:8px">Your converted recording</h3><p class="vc-help">Review the result for changes to words, timing, pitch, and emotional delivery.</p><audio controls preload="metadata"></audio><div class="actions"><button id="vc-download" class="btn secondary" type="button">Download WAV</button><button id="vc-open-editor" class="btn primary" type="button">Open in Audio Editor</button></div></div>';
    result.querySelector("audio").src=outputUrl;
    result.querySelector("#vc-download").addEventListener("click",()=>{const a=document.createElement("a");a.href=outputUrl;a.download=outputFile.name;document.body.appendChild(a);a.click();a.remove();});
    result.querySelector("#vc-open-editor").addEventListener("click",()=>{if(typeof window.nav==="function")window.nav("tools");window.dispatchEvent(new CustomEvent("audiolab:open-in-editor",{detail:{file:outputFile}}));});
  }

  function mountLibrary() {
    const page=document.getElementById("page-voices");if(!page||page.querySelector("#vc-target-library"))return;
    const section=document.createElement("section");section.id="vc-target-library";section.className="card";section.style.marginTop="18px";
    section.innerHTML='<div class="eyebrow">Voice Convert references</div><h3 style="margin-top:9px">Saved target voices</h3><p class="muted">Separate from IndicF5 source-voice profiles. Reference audio is stored locally in this browser, not uploaded to a cloud library.</p>' +
      '<div class="vc-layout"><div class="vc-field"><label for="vc-lib-file">Add target reference</label><input id="vc-lib-file" type="file" accept="audio/*"><div id="vc-lib-info" class="vc-help">Choose a reference recording.</div></div><div class="vc-field"><label for="vc-lib-name">Saved voice name</label><input id="vc-lib-name" type="text" maxlength="80" placeholder="e.g. Raspy energetic style"><button id="vc-lib-save" class="btn primary" type="button">Save target voice</button></div></div>' +
      '<div id="vc-target-list" class="vc-voice-list"><p class="vc-help">Loading saved voices…</p></div>';
    page.appendChild(section);
    let draft=null;
    section.querySelector("#vc-lib-file").addEventListener("change",e=>{draft=e.target.files&&e.target.files[0]||null;section.querySelector("#vc-lib-info").textContent=draft?draft.name+" · "+(draft.size/1048576).toFixed(2)+" MB":"Choose a reference recording.";});
    section.querySelector("#vc-lib-save").addEventListener("click",async()=>{if(!draft)return toast("Choose a target voice reference first.");try{await saveVoice(draft,section.querySelector("#vc-lib-name").value);draft=null;section.querySelector("#vc-lib-file").value="";section.querySelector("#vc-lib-name").value="";section.querySelector("#vc-lib-info").textContent="Reference saved locally.";await refreshLibrary();toast("Target voice saved locally.");}catch(e){toast(e.message||"Could not save target voice.");}});
    renderLibrary(section);
  }
  async function renderLibrary(section) {
    const root=section||document.getElementById("vc-target-library"),list=root&&root.querySelector("#vc-target-list");if(!list)return;
    previewUrls.forEach(u=>URL.revokeObjectURL(u));previewUrls=[];
    const voices=await allVoices();
    if(!voices.length){list.innerHTML='<div class="empty">No target references saved yet. Add one above or save a target from Studio.</div>';return;}
    list.innerHTML=voices.map(v=>'<div class="vc-target-row"><div><strong>'+esc(v.name)+'</strong><small>'+esc(v.fileName)+' · '+(Number(v.size||0)/1048576).toFixed(2)+' MB · Saved in this browser</small><audio controls preload="none" data-preview="'+esc(v.id)+'" style="display:block;width:100%;max-width:460px;margin-top:10px"></audio></div><div class="vc-target-actions"><button class="btn primary" type="button" data-use="'+esc(v.id)+'">Use in Studio</button><button class="btn secondary" type="button" data-rename="'+esc(v.id)+'">Rename</button><button class="btn secondary" type="button" data-delete="'+esc(v.id)+'">Delete</button></div></div>').join("");
    voices.forEach(v=>{const audio=list.querySelector('[data-preview="'+v.id+'"]');if(audio&&v.blob){const url=URL.createObjectURL(v.blob);previewUrls.push(url);audio.src=url;}});
    list.querySelectorAll("[data-use]").forEach(b=>b.addEventListener("click",()=>{selectedVoiceId=b.dataset.use;targetFile=null;if(typeof window.nav==="function")window.nav("studio");setTimeout(()=>{const c=document.getElementById("voiceConvertDashboard");if(c)fillTargetSelect(c);},80);}));
    list.querySelectorAll("[data-rename]").forEach(b=>b.addEventListener("click",async()=>{const v=voices.find(x=>x.id===b.dataset.rename);if(!v)return;const name=prompt("Rename this target voice:",v.name);if(name===null||!name.trim())return;try{await changeVoice(v.id,"rename",name);await refreshLibrary();const c=document.getElementById("voiceConvertDashboard");if(c)await fillTargetSelect(c);toast("Target voice renamed.");}catch(e){toast(e.message||"Rename failed.");}}));
    list.querySelectorAll("[data-delete]").forEach(b=>b.addEventListener("click",async()=>{const v=voices.find(x=>x.id===b.dataset.delete);if(!v||!confirm('Delete saved target voice "'+v.name+'" from this browser?'))return;try{await changeVoice(v.id,"delete");await refreshLibrary();const c=document.getElementById("voiceConvertDashboard");if(c)await fillTargetSelect(c);toast("Saved target voice deleted.");}catch(e){toast(e.message||"Delete failed.");}}));
  }
  async function refreshLibrary(){const s=document.getElementById("vc-target-library");if(s)await renderLibrary(s);const c=document.getElementById("voiceConvertDashboard");if(c)await fillTargetSelect(c);}

  function mountModels() {
    const page=document.getElementById("page-models");if(!page||page.querySelector("#vc-model-status-card"))return;
    const card=document.createElement("section");card.id="vc-model-status-card";card.className="card";card.style.marginTop="18px";
    card.innerHTML='<div class="eyebrow">Voice conversion model</div><h3 style="margin-top:9px">OpenVoice V1 · Audio-to-audio</h3><p class="muted">Changes vocal timbre using a target reference. It is separate from IndicF5 text-to-speech.</p><div id="vc-model-state" class="vc-model-state">Checking local backend…</div><p id="vc-model-details" class="vc-help" style="margin-top:12px">Waiting for the local status response.</p><p class="vc-note">OpenVoice V1 code is MIT-licensed. Checkpoint weights and dependencies are installed locally. CPU inference may be slow.</p><p class="vc-help">Setup command: <code>.\scripts\setup-voice-conversion.ps1</code></p>';
    page.appendChild(card);modelStatus(card);
  }
  function modelLabel(m){if(!m)return "Model not reported by backend.";if(m.state==="loaded")return "Loaded and ready";if(m.state==="ready_to_load")return "Installed; loads on first conversion";if(m.state==="model_files_missing")return "Model checkpoint files missing — run setup script";if(m.state==="dependencies_missing")return "OpenVoice dependencies missing — run setup script";return "Model state: "+(m.state||"unknown");}
  async function modelStatus(card) {
    if(!card)return;const state=card.querySelector("#vc-backend-state")||card.querySelector("#vc-model-state"),details=card.querySelector("#vc-model-details"),base=apiBase();
    if(!base){if(state)state.textContent="Local backend required";if(details)details.textContent="This static site does not provide free cloud inference. Run START-AUDIOLAB.bat on the Windows PC that processes audio.";return;}
    try{const response=await fetch(base+"/models",{cache:"no-store"});if(!response.ok)throw new Error("Local backend returned HTTP "+response.status);const data=await response.json(),m=(data.models||[]).find(x=>x.id==="openvoice-v1");if(state)state.textContent=modelLabel(m);if(details)details.textContent=m?"State: "+m.state+". Model files: "+(m.model_files_present?"present":"missing")+". Package: "+(m.package_installed?"installed":"missing")+". Device: "+(m.device||"unknown")+".":"Backend did not report OpenVoice.";}
    catch(e){if(state)state.textContent="Local backend offline";if(details)details.textContent=(e.message||e)+". Start/restart START-AUDIOLAB.bat and check http://127.0.0.1:8000/health.";}
  }
  function mount(){mountStudio();mountLibrary();mountModels();}
  new MutationObserver(mount).observe(document.body,{childList:true,subtree:true});
  window.addEventListener("load",mount);
  setTimeout(mount,250);
})();
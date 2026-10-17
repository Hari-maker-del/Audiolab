(() => {
  "use strict";
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
  const root = document.getElementById("audiolab-pages");
  if (!root || !window.AudiolabCloud) return;
  const cloud = window.AudiolabCloud;
  const path = () => location.pathname.replace(/\/+$/, "") || "/";
  const projectId = () => decodeURIComponent(path().split("/")[2] || "");
  const fmtDate = value => value ? new Date(value).toLocaleString() : "";
  const bytes = n => n < 1024*1024 ? Math.max(1,Math.round(n/1024)) + " KB" : (n/1024/1024).toFixed(1) + " MB";
  const note = (text, bad = false) => { const el = document.getElementById("cloud-message"); if (el) { el.textContent = text; el.style.color = bad ? "#b45309" : "var(--muted,#777)"; el.hidden = false; } };
  const frame = (title, subtitle, body) => {
    root.innerHTML = '<header class="topbar"><a class="brand" href="/dashboard"><span class="brand-mark">≈</span><span>Audiolab</span></a><nav><a href="/projects">Projects</a><a href="/studio.html">Studio</a><button class="button" id="cloud-signout">Sign out</button></nav></header><div class="app-layout"><aside class="sidebar"><a class="brand" href="/dashboard"><span class="brand-mark">≈</span><span>Audiolab</span></a><a class="open-studio" href="/studio.html">♫ &nbsp; Voice Studio</a><nav><a class="side-link" href="/dashboard">Dashboard</a><a class="side-link" href="/projects">Projects</a><a class="side-link" href="/projects/new">New project</a><a class="side-link" href="/ai/voice">AI Voice</a></nav><div class="sidebar-foot">Cloud workspace · private assets</div></aside><main class="workspace"><div class="workspace-head"><div><span class="eyebrow">CLOUD WORKSPACE</span><h1>'+esc(title)+'</h1><p class="lead">'+esc(subtitle)+'</p></div><a class="button primary" href="/projects/new">＋ New project</a></div>'+body+'<footer>Audiolab · Your projects are private to your account <a href="/privacy">Privacy</a></footer></main></div>';
    document.getElementById("cloud-signout")?.addEventListener("click", async () => {
      const button = document.getElementById("cloud-signout"); button.disabled = true;
      try { await cloud.signOut(); location.href = "/login"; } catch (error) { note(error.message, true); button.disabled = false; }
    });
  };
  async function dashboard() {
    const projects = await cloud.listProjects();
    const cards = projects.length ? projects.map(p => '<a class="project-card" href="/projects/'+encodeURIComponent(p.id)+'/editor"><span class="project-icon">♫</span><b>'+esc(p.name)+'</b><small>'+esc(p.kind)+' · '+esc(fmtDate(p.updated_at))+'</small><span class="tag">Cloud project</span></a>').join("") : '<div class="empty"><div class="project-icon">♫</div><h3>Your cloud studio is ready</h3><p>Create a project, upload audio, or save generated speech from the Studio.</p><a class="button primary" href="/projects/new">Create your first project</a></div>';
    frame(path() === "/dashboard" ? "Your workspace" : "Your projects", "Signed in · projects and audio are stored in your cloud account.", '<div class="stats"><div class="stat"><span>Projects</span><b>'+projects.length+'</b><small>Synced to your account</small></div><div class="stat"><span>Storage</span><b>Private</b><small>Authenticated access</small></div><div class="stat"><span>AI</span><b>Hosted</b><small>Provider availability varies</small></div></div><div class="section-head"><div><h2>Projects</h2><p>Available wherever you sign in.</p></div><a class="button primary" href="/projects/new">＋ New project</a></div><div class="project-grid">'+cards+'</div>');
  }
  async function newProject() {
    frame("Create a cloud project", "Project metadata is saved to your account. Audio can be uploaded after creation.", '<form id="cloud-new-project" class="form-card"><label for="cloud-project-name">Project name</label><input id="cloud-project-name" maxlength="120" required placeholder="e.g. Tamil podcast intro"><label for="cloud-project-kind">Workflow</label><select id="cloud-project-kind"><option>Audio editing</option><option>Voice generation</option><option>Podcast</option><option>Music and stems</option><option>Dubbing and transcript</option></select><p id="cloud-message" class="hint" hidden></p><button class="button primary" id="cloud-create-button">Create project</button></form>');
    document.getElementById("cloud-new-project").addEventListener("submit", async event => {
      event.preventDefault();
      const button = document.getElementById("cloud-create-button"); button.disabled = true; button.textContent = "Creating…";
      try { const p = await cloud.createProject({ name: document.getElementById("cloud-project-name").value, kind: document.getElementById("cloud-project-kind").value }); location.href = "/projects/"+encodeURIComponent(p.id)+"/editor"; }
      catch (error) { note(error.message || "Could not create project.", true); button.disabled = false; button.textContent = "Create project"; }
    });
  }
  async function editor() {
    const id = projectId();
    const [project, assets] = await Promise.all([cloud.getProject(id), cloud.listAssets(id)]);
    const audioRows = await Promise.all(assets.map(async asset => {
      let url = "";
      try { url = await cloud.signedAssetUrl(asset.id); } catch (_) {}
      return '<article class="feature-card" style="margin:12px 0"><b>'+esc(asset.file_name)+'</b><p class="hint">'+esc(bytes(asset.byte_size))+' · '+esc(asset.asset_kind)+' · private audio</p>'+(url ? '<audio controls preload="none" style="width:100%" src="'+esc(url)+'"></audio>' : '<p class="hint">Audio URL unavailable; check storage policies.</p>')+'</article>';
    })).join("");
    frame("Project timeline", "Cloud-saved project · upload and listen to audio assets from any signed-in device.", '<div class="editor-placeholder"><div class="editor-toolbar"><a class="button" href="/projects">← Projects</a><span class="tag">Cloud project</span></div><div class="form-card"><label for="cloud-edit-name">Project name</label><input id="cloud-edit-name" maxlength="120" value="'+esc(project.name)+'"><label for="cloud-edit-notes">Notes / script</label><textarea id="cloud-edit-notes" rows="5" placeholder="Add the script, recording notes, or production brief">'+esc(project.notes || "")+'</textarea><div class="actions" style="display:flex;gap:10px;flex-wrap:wrap;margin-top:12px"><button class="button primary" id="cloud-save-project">Save project</button><label class="button" for="cloud-audio-upload">＋ Upload audio</label><input id="cloud-audio-upload" type="file" accept="audio/*,.wav,.mp3,.flac,.m4a,.ogg,.webm" hidden><button class="button" id="cloud-delete-project">Delete project</button></div><p id="cloud-message" class="hint" hidden></p></div><div class="section-head"><div><h2>Audio assets</h2><p>Private files stored in cloud object storage.</p></div></div>'+(audioRows || '<div class="empty"><h3>No audio assets yet</h3><p>Upload an audio file or generate a voice in Studio and choose Save to Project.</p></div>')+'</div>');
    document.getElementById("cloud-save-project").addEventListener("click", async event => {
      const button = event.currentTarget; button.disabled = true;
      try { await cloud.saveProject(id, { name: document.getElementById("cloud-edit-name").value, notes: document.getElementById("cloud-edit-notes").value }); note("Project saved to the cloud."); }
      catch (error) { note(error.message, true); }
      finally { button.disabled = false; }
    });
    document.getElementById("cloud-audio-upload").addEventListener("change", async event => {
      const file = event.target.files?.[0]; if (!file) return;
      try {
        note("Uploading audio privately…");
        await cloud.uploadAudio({ projectId: id, blob: file, filename: file.name, assetKind: "uploaded" });
        location.reload();
      } catch (error) { note(error.message || "Audio upload failed.", true); event.target.value = ""; }
    });
    document.getElementById("cloud-delete-project").addEventListener("click", async event => {
      if (!confirm("Delete this cloud project and its stored audio assets? This cannot be undone.")) return;
      const button = event.currentTarget; button.disabled = true;
      try { await cloud.deleteProject(id); location.href = "/projects"; }
      catch (error) { note(error.message || "Could not delete project.", true); button.disabled = false; }
    });
  }
  async function authForm() {
    const p = path();
    const form = document.getElementById("auth-form");
    if (!form) return;
    const submit = form.querySelector('button[type="submit"],button:not([type])');
    const status = document.createElement("p");
    status.id = "cloud-auth-message"; status.className = "hint"; status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
    form.appendChild(status);
    form.addEventListener("submit", async event => {
      event.preventDefault(); event.stopImmediatePropagation();
      const fields = new FormData(form);
      if (submit) { submit.disabled = true; submit.textContent = "Please wait…"; }
      status.textContent = "Connecting to secure cloud authentication…";
      try {
        if (p === "/signup") {
          const result = await cloud.signUp({ name: fields.get("name"), email: fields.get("email"), password: fields.get("password") });
          status.textContent = result.needsEmailConfirmation ? "Account created. Check your email to verify it, then sign in." : "Account created. Opening your workspace…";
          if (!result.needsEmailConfirmation) setTimeout(() => { location.href = "/dashboard"; }, 350);
        } else if (p === "/login") {
          await cloud.signIn({ email: fields.get("email"), password: fields.get("password") });
          location.href = "/dashboard";
        } else if (p === "/forgot-password") {
          await cloud.resetPassword(fields.get("email"));
          status.textContent = "If the email is registered, a password-reset link will be sent.";
        } else if (p === "/reset-password") {
          await cloud.updatePassword(fields.get("password"));
          status.textContent = "Password updated. You can sign in with your new password.";
        } else {
          status.textContent = "Open the verification link from your email, then sign in.";
        }
      } catch (error) {
        status.textContent = error.message || "Authentication failed.";
        status.style.color = "#b45309";
      } finally {
        if (submit) { submit.disabled = false; submit.textContent = p === "/signup" ? "Create account" : p === "/login" ? "Sign in" : "Continue"; }
      }
    }, true);
  }
  async function run() {
    try {
      const result = await cloud.init();
      if (!result.configured) {
        if (["/signup","/login","/forgot-password","/reset-password"].includes(path())) {
          const host = document.querySelector(".form-card");
          if (host && !host.querySelector(".cloud-config-warning")) {
            const warning = document.createElement("div"); warning.className = "notice cloud-config-warning";
            warning.innerHTML = "<b>Cloud setup required</b><p>Add your Supabase project URL and publishable key to <code>frontend/cloud-config.js</code>, then apply the SQL migration in <code>supabase/migrations</code>. No account will be simulated before setup.</p>";
            host.prepend(warning);
          }
        }
        return;
      }
      const user = await cloud.getUser();
      if (["/signup","/login"].includes(path()) && user) { location.replace("/dashboard"); return; }
      if (["/signup","/login","/forgot-password","/reset-password","/verify","/auth/callback"].includes(path())) { await authForm(); return; }
      if (["/dashboard","/projects"].includes(path())) {
        if (!user) { location.replace("/login?next="+encodeURIComponent(path())); return; }
        await dashboard(); return;
      }
      if (path() === "/projects/new") {
        if (!user) { location.replace("/login?next=%2Fprojects%2Fnew"); return; }
        await newProject(); return;
      }
      if (/^\/projects\/[^/]+\/editor$/.test(path())) {
        if (!user) { location.replace("/login?next="+encodeURIComponent(path())); return; }
        await editor(); return;
      }
    } catch (error) {
      const host = document.querySelector(".form-card") || root;
      const warning = document.createElement("div"); warning.className = "notice";
      warning.textContent = "Audiolab cloud could not initialize: " + (error.message || "check cloud configuration.");
      host.prepend(warning);
    }
  }
  run();
})();

(() => {
  "use strict";
  const config = window.AUDIOLAB_CLOUD_CONFIG || {};
  const MAX_BYTES = 100 * 1024 * 1024;
  const configured = Boolean(config.supabaseUrl && config.supabaseAnonKey);
  let client = null;
  let session = null;
  let initPromise = null;

  const safeName = value => String(value || "audio.wav").replace(/[^a-zA-Z0-9._-]/g, "_").slice(-120) || "audio.wav";
  const message = (text, kind = "info") => window.dispatchEvent(new CustomEvent("audiolab-cloud-message", { detail: { text, kind } }));

  function init() {
    if (initPromise) return initPromise;
    initPromise = (async () => {
      if (!configured) return { configured: false, session: null };
      if (!window.supabase?.createClient) throw new Error("Supabase client library did not load. Check the network and refresh.");
      client = window.supabase.createClient(config.supabaseUrl, config.supabaseAnonKey, {
        auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true }
      });
      const { data, error } = await client.auth.getSession();
      if (error) throw error;
      session = data.session || null;
      client.auth.onAuthStateChange((_event, nextSession) => {
        session = nextSession || null;
        window.dispatchEvent(new CustomEvent("audiolab-cloud-auth-change", { detail: { user: session?.user || null } }));
      });
      return { configured: true, session };
    })().catch(error => {
      initPromise = null;
      throw error;
    });
    return initPromise;
  }

  async function requireClient() {
    await init();
    if (!client) throw new Error("Audiolab cloud is not configured yet. Add the Supabase project URL and publishable/anon key to frontend/cloud-config.js.");
    return client;
  }
  async function requireUser() {
    const c = await requireClient();
    const { data, error } = await c.auth.getUser();
    if (error || !data?.user) throw new Error("Sign in to save projects to your cloud workspace.");
    session = (await c.auth.getSession()).data.session;
    return { c, user: data.user };
  }

  async function signUp({ email, password, name }) {
    const c = await requireClient();
    const { data, error } = await c.auth.signUp({
      email: String(email || "").trim(),
      password,
      options: {
        emailRedirectTo: location.origin + "/auth/callback",
        data: { display_name: String(name || "").trim().slice(0, 80) }
      }
    });
    if (error) throw error;
    if (data.session) session = data.session;
    return { user: data.user, needsEmailConfirmation: !data.session };
  }
  async function signIn({ email, password }) {
    const c = await requireClient();
    const { data, error } = await c.auth.signInWithPassword({ email: String(email || "").trim(), password });
    if (error) throw error;
    session = data.session;
    return data.user;
  }
  async function signOut() {
    const c = await requireClient();
    const { error } = await c.auth.signOut();
    if (error) throw error;
    session = null;
  }
  async function resetPassword(email) {
    const c = await requireClient();
    const { error } = await c.auth.resetPasswordForEmail(String(email || "").trim(), { redirectTo: location.origin + "/reset-password" });
    if (error) throw error;
  }
  async function updatePassword(password) {
    const c = await requireClient();
    const { error } = await c.auth.updateUser({ password });
    if (error) throw error;
  }
  async function getUser() {
    try {
      await init();
      if (!client) return null;
      const { data, error } = await client.auth.getUser();
      if (error) return null;
      return data.user || null;
    } catch (_) { return null; }
  }

  async function createProject({ name, kind, notes = "", timeline = { tracks: [], volume: 1 } }) {
    const { c, user } = await requireUser();
    const row = { owner_id: user.id, name: String(name || "Untitled project").trim().slice(0, 120), kind: String(kind || "Audio editing"), notes: String(notes || ""), timeline };
    if (!row.name) throw new Error("Enter a project name first.");
    const { data, error } = await c.from("audiolab_projects").insert(row).select("*").single();
    if (error) throw error;
    return data;
  }
  async function listProjects() {
    const { c } = await requireUser();
    const { data, error } = await c.from("audiolab_projects").select("id,name,kind,notes,timeline,created_at,updated_at").order("updated_at", { ascending: false }).limit(200);
    if (error) throw error;
    return data || [];
  }
  async function getProject(projectId) {
    const { c } = await requireUser();
    const { data, error } = await c.from("audiolab_projects").select("*").eq("id", projectId).single();
    if (error) throw error;
    return data;
  }
  async function saveProject(projectId, patch) {
    const { c } = await requireUser();
    const allowed = {};
    ["name", "kind", "notes", "timeline"].forEach(key => { if (Object.prototype.hasOwnProperty.call(patch || {}, key)) allowed[key] = patch[key]; });
    allowed.updated_at = new Date().toISOString();
    const { data, error } = await c.from("audiolab_projects").update(allowed).eq("id", projectId).select("*").single();
    if (error) throw error;
    return data;
  }
  async function deleteProject(projectId) {
    const { c } = await requireUser();
    const { data: assets, error: listError } = await c.from("audiolab_audio_assets").select("storage_path").eq("project_id", projectId);
    if (listError) throw listError;
    if (assets?.length) {
      const { error: removeError } = await c.storage.from("audiolab-audio").remove(assets.map(asset => asset.storage_path));
      if (removeError) throw removeError;
    }
    const { error } = await c.from("audiolab_projects").delete().eq("id", projectId);
    if (error) throw error;
  }
  async function uploadAudio({ projectId, blob, filename, assetKind = "audio", durationSeconds = null }) {
    if (!(blob instanceof Blob) || !blob.size) throw new Error("Choose a non-empty audio file.");
    if (blob.size > MAX_BYTES) throw new Error("Audio uploads are limited to 100 MB per file.");
    const { c, user } = await requireUser();
    const assetId = crypto.randomUUID();
    const fileName = safeName(filename);
    const storagePath = user.id + "/" + projectId + "/" + assetId + "/" + fileName;
    const { error: uploadError } = await c.storage.from("audiolab-audio").upload(storagePath, blob, {
      contentType: blob.type || "application/octet-stream", upsert: false
    });
    if (uploadError) throw uploadError;
    const row = {
      id: assetId, owner_id: user.id, project_id: projectId, storage_path: storagePath,
      file_name: fileName, mime_type: blob.type || "application/octet-stream",
      byte_size: blob.size, duration_seconds: Number.isFinite(durationSeconds) ? durationSeconds : null,
      asset_kind: assetKind
    };
    const { data, error } = await c.from("audiolab_audio_assets").insert(row).select("*").single();
    if (error) {
      await c.storage.from("audiolab-audio").remove([storagePath]);
      throw error;
    }
    return data;
  }
  async function listAssets(projectId) {
    const { c } = await requireUser();
    let query = c.from("audiolab_audio_assets").select("id,project_id,file_name,mime_type,byte_size,duration_seconds,asset_kind,storage_path,created_at").order("created_at", { ascending: true });
    if (projectId) query = query.eq("project_id", projectId);
    const { data, error } = await query;
    if (error) throw error;
    return data || [];
  }
  async function signedAssetUrl(assetId) {
    const { c } = await requireUser();
    const { data: asset, error: lookupError } = await c.from("audiolab_audio_assets").select("storage_path").eq("id", assetId).single();
    if (lookupError) throw lookupError;
    const { data, error } = await c.storage.from("audiolab-audio").createSignedUrl(asset.storage_path, 300);
    if (error) throw error;
    return data.signedUrl;
  }
  async function enqueueJob({ projectId = null, jobType, input = {}, provider = "hosted-free" }) {
    const { c, user } = await requireUser();
    const { data, error } = await c.from("audiolab_processing_jobs").insert({
      owner_id: user.id, project_id: projectId, job_type: jobType, input, provider
    }).select("*").single();
    if (error) throw error;
    return data;
  }

  async function createProjectFromAudio({ blob, filename, name, kind, notes, durationSeconds = null }) {
    const project = await createProject({ name, kind, notes });
    try {
      const asset = await uploadAudio({ projectId: project.id, blob, filename, assetKind: "generated", durationSeconds });
      return { id: project.id, name: project.name, editorUrl: "/projects/" + encodeURIComponent(project.id) + "/editor", project, asset, cloud: true };
    } catch (error) {
      try { await deleteProject(project.id); } catch (_) {}
      throw error;
    }
  }

  window.AudiolabCloud = {
    configured, init, signUp, signIn, signOut, resetPassword, updatePassword, getUser,
    createProject, listProjects, getProject, saveProject, deleteProject, uploadAudio,
    listAssets, signedAssetUrl, enqueueJob, createProjectFromAudio
  };
  init().then(result => {
    window.dispatchEvent(new CustomEvent("audiolab-cloud-ready", { detail: result }));
  }).catch(error => message(error.message || "Cloud initialization failed", "error"));
})();

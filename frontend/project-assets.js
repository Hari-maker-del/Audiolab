(() => {
  "use strict";
  const DB_NAME = "audiolab-mvp";
  const DB_VERSION = 1;
  const MAX_FILE_BYTES = 100 * 1024 * 1024;
  const AUDIO_EXT = /\.(wav|mp3|m4a|aac|ogg|oga|flac|webm|aiff|aif)$/i;
  const stamp = () => new Date().toISOString();
  const makeId = () => crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
  function openDB() {
    return new Promise((resolve, reject) => {
      if (!("indexedDB" in window)) return reject(new Error("This browser does not support persistent local projects."));
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains("projects")) db.createObjectStore("projects", { keyPath: "id" });
        if (!db.objectStoreNames.contains("exports")) db.createObjectStore("exports", { keyPath: "id" });
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error("Could not open local project storage."));
    });
  }
  async function read(id) {
    const db = await openDB();
    try {
      return await new Promise((resolve, reject) => {
        const tx = db.transaction("projects", "readonly");
        const req = tx.objectStore("projects").get(id);
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => reject(req.error || new Error("Could not load the project."));
        tx.oncomplete = () => db.close();
        tx.onabort = () => reject(tx.error || new Error("Project read was cancelled."));
      });
    } catch (error) { db.close(); throw error; }
  }
  async function write(project) {
    const db = await openDB();
    try {
      await new Promise((resolve, reject) => {
        const tx = db.transaction("projects", "readwrite");
        tx.objectStore("projects").put(project);
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error || new Error("Could not save the project."));
        tx.onabort = () => reject(tx.error || new Error("Project save was cancelled."));
      });
      return project;
    } finally { db.close(); }
  }
  function routeToEditor(id) {
    const path = "/projects/" + encodeURIComponent(id) + "/editor";
    const localStatic = (location.hostname === "127.0.0.1" || location.hostname === "localhost") && location.port === "5500";
    return localStatic ? "/app-pages.html#" + path : path;
  }
  function validateAudio(blob, name) {
    if (!blob || typeof blob.size !== "number" || blob.size <= 44) throw new Error("The generated audio file is empty.");
    if (blob.size > MAX_FILE_BYTES) throw new Error("This audio file exceeds the 100 MB local project limit.");
    const filename = String(name || "audiolab-generated.wav");
    if (!(blob.type || "").startsWith("audio/") && !AUDIO_EXT.test(filename)) throw new Error("Choose a supported audio file.");
    return filename;
  }
  async function durationOf(blob) {
    return new Promise(resolve => {
      const url = URL.createObjectURL(blob);
      const audio = new Audio();
      audio.preload = "metadata";
      audio.onloadedmetadata = () => { const duration = Number.isFinite(audio.duration) ? audio.duration : null; URL.revokeObjectURL(url); resolve(duration); };
      audio.onerror = () => { URL.revokeObjectURL(url); resolve(null); };
      audio.src = url;
    });
  }
  async function createProjectFromAudio(options) {
    const config = options || {};
    const blob = config.blob;
    const filename = validateAudio(blob, config.filename);
    const now = stamp();
    const id = makeId();
    const trackId = makeId();
    const duration = await durationOf(blob);
    const track = { id: trackId, name: filename, audioBlob: blob, audioType: blob.type || "audio/wav", duration, offset: 0, gain: 1, muted: false, createdAt: now, origin: config.origin || "generated" };
    const project = {
      id,
      name: String(config.name || "Generated voice project").trim().slice(0, 80) || "Generated voice project",
      kind: String(config.kind || "Voice generation"),
      created: new Date().toLocaleString(),
      createdAt: now,
      updatedAt: now,
      audioBlob: blob,
      audioName: filename,
      audioType: blob.type || "audio/wav",
      duration,
      notes: String(config.notes || ""),
      editor: { volume: 1 },
      tracks: [track],
      activeTrackId: trackId,
      source: "audiolab-generated"
    };
    await write(project);
    try {
      const index = JSON.parse(localStorage.getItem("audiolab-projects") || "[]");
      localStorage.setItem("audiolab-projects", JSON.stringify([{ id, name: project.name, kind: project.kind, created: project.created, updatedAt: now, hasAudio: true, audioName: filename, audioType: project.audioType, size: blob.size, duration }, ...index.filter(item => item.id !== id)].slice(0, 200)));
    } catch (_) {}
    return { id, name: project.name, editorUrl: routeToEditor(id), project };
  }
  async function addTrack(projectId, file, options) {
    const filename = validateAudio(file, file && file.name);
    const project = await read(projectId);
    if (!project) throw new Error("Project not found in this browser.");
    const config = options || {};
    const track = {
      id: makeId(), name: filename, audioBlob: file, audioType: file.type || "audio/wav",
      duration: await durationOf(file), offset: Math.max(0, Number(config.offset) || 0),
      gain: 1, muted: false, createdAt: stamp(), origin: config.origin || "imported"
    };
    project.tracks = Array.isArray(project.tracks) ? project.tracks : [];
    project.tracks.push(track);
    if (!project.audioBlob) {
      project.audioBlob = file; project.audioName = filename; project.audioType = track.audioType; project.duration = track.duration;
    }
    project.updatedAt = stamp();
    await write(project);
    return track;
  }
  window.AudiolabProjectAssets = { createProjectFromAudio, addTrack, getProject: read, saveProject: write, routeToEditor };
})();
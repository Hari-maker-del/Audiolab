(() => {
  "use strict";
  const DB_NAME = "audiolab-local";
  const DB_VERSION = 2;
  const ACTIVE_STORE = "voice-reference";
  const PROFILE_STORE = "voice-profiles";
  const ACTIVE_KEY = "active";
  let restoring = false;

  function openDB() {
    return new Promise((resolve, reject) => {
      if (!window.indexedDB) return reject(new Error("IndexedDB unavailable"));
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(ACTIVE_STORE)) db.createObjectStore(ACTIVE_STORE);
        if (!db.objectStoreNames.contains(PROFILE_STORE)) db.createObjectStore(PROFILE_STORE, { keyPath: "id" });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error || new Error("IndexedDB open failed"));
    });
  }

  async function putActive(file) {
    if (!file) return false;
    const db = await openDB();
    try {
      await new Promise((resolve, reject) => {
        const tx = db.transaction(ACTIVE_STORE, "readwrite");
        tx.objectStore(ACTIVE_STORE).put({
          blob: file, name: file.name || "voice-reference",
          type: file.type || "audio/wav", savedAt: Date.now()
        }, ACTIVE_KEY);
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error || new Error("Could not save active voice reference"));
      });
      return true;
    } finally { db.close(); }
  }

  async function getActive() {
    const db = await openDB();
    try {
      return await new Promise((resolve, reject) => {
        const req = db.transaction(ACTIVE_STORE, "readonly").objectStore(ACTIVE_STORE).get(ACTIVE_KEY);
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => reject(req.error || new Error("Could not restore active voice reference"));
      });
    } finally { db.close(); }
  }

  async function saveProfile(profile) {
    if (!profile || !profile.file) throw new Error("A voice reference file is required.");
    const row = {
      id: String(profile.id || (crypto.randomUUID ? crypto.randomUUID() : "voice-" + Date.now())),
      name: String(profile.name || "My voice").trim().slice(0, 80) || "My voice",
      language: String(profile.language || "Tamil"),
      duration: String(profile.duration || "Reference audio"),
      fileName: String(profile.file.name || "voice-reference.wav"),
      type: String(profile.file.type || "audio/wav"),
      size: Number(profile.file.size || 0),
      createdAt: Number(profile.createdAt || Date.now()),
      blob: profile.file
    };
    const db = await openDB();
    try {
      await new Promise((resolve, reject) => {
        const tx = db.transaction(PROFILE_STORE, "readwrite");
        tx.objectStore(PROFILE_STORE).put(row);
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error || new Error("Could not save voice profile"));
      });
    } finally { db.close(); }
    await putActive(profile.file);
    return { ...row, blob: undefined };
  }

  async function listProfiles() {
    const db = await openDB();
    try {
      const rows = await new Promise((resolve, reject) => {
        const req = db.transaction(PROFILE_STORE, "readonly").objectStore(PROFILE_STORE).getAll();
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => reject(req.error || new Error("Could not load voice profiles"));
      });
      return rows.sort((a, b) => b.createdAt - a.createdAt).map(({ blob, ...meta }) => meta);
    } finally { db.close(); }
  }

  async function getProfile(id) {
    const db = await openDB();
    try {
      return await new Promise((resolve, reject) => {
        const req = db.transaction(PROFILE_STORE, "readonly").objectStore(PROFILE_STORE).get(String(id));
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => reject(req.error || new Error("Could not load selected voice profile"));
      });
    } finally { db.close(); }
  }

  async function renameProfile(id, name) {
    const row = await getProfile(id);
    if (!row) throw new Error("Voice profile not found.");
    row.name = String(name || "").trim().slice(0, 80);
    if (!row.name) throw new Error("Voice profile name cannot be empty.");
    const db = await openDB();
    try {
      await new Promise((resolve, reject) => {
        const tx = db.transaction(PROFILE_STORE, "readwrite");
        tx.objectStore(PROFILE_STORE).put(row);
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error || new Error("Could not rename voice profile"));
      });
    } finally { db.close(); }
    return { id: row.id, name: row.name, language: row.language, duration: row.duration, fileName: row.fileName, type: row.type, size: row.size, createdAt: row.createdAt };
  }

  async function deleteProfile(id) {
    const db = await openDB();
    try {
      await new Promise((resolve, reject) => {
        const tx = db.transaction(PROFILE_STORE, "readwrite");
        tx.objectStore(PROFILE_STORE).delete(String(id));
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error || new Error("Could not delete voice profile"));
      });
    } finally { db.close(); }
  }

  window.audiolabVoiceProfiles = { save: saveProfile, list: listProfiles, get: getProfile, rename: renameProfile, delete: deleteProfile };

  async function restoreReference() {
    if (restoring || window.__audiolabVoiceHydrated) return false;
    restoring = true;
    try {
      const saved = await getActive();
      if (!saved?.blob) return false;
      const file = saved.blob instanceof File ? saved.blob : new File([saved.blob], saved.name || "audiolab-voice-reference.wav", { type: saved.type || saved.blob.type || "audio/wav" });
      const originalNav = window.__audiolabOriginalNav || window.nav;
      originalNav?.("voices");
      await new Promise(resolve => setTimeout(resolve, 180));
      const input = document.getElementById("voiceFile");
      if (!input) return false;
      const dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
      input.dispatchEvent(new Event("change", { bubbles: true }));
      await new Promise(resolve => setTimeout(resolve, 250));
      window.__audiolabVoiceHydrated = true;
      return true;
    } catch (_) {
      return false;
    } finally { restoring = false; }
  }

  document.addEventListener("change", async event => {
    const input = event.target;
    if (input?.id !== "voiceFile" || !input.files?.[0]) return;
    try {
      const ok = await putActive(input.files[0]);
      window.__audiolabVoiceHydrated = true;
      if (!ok) throw new Error("Storage unavailable");
    } catch (_) {
      const toast = document.getElementById("toast");
      if (toast) {
        toast.textContent = "Voice selected. Browser storage is unavailable; keep this tab open.";
        toast.classList.add("show");
        setTimeout(() => toast.classList.remove("show"), 2800);
      }
    }
  }, true);

  const originalNav = window.nav;
  if (typeof originalNav === "function") {
    window.__audiolabOriginalNav = originalNav;
    window.nav = async function(page) {
      if (page === "generate" && !window.__audiolabVoiceHydrated) await restoreReference();
      return originalNav(page);
    };
  }
  setTimeout(() => restoreReference().catch(() => {}), 350);
})();

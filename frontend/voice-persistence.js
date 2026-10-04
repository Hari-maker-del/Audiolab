(() => {
  const DB_NAME = 'audiolab-local';
  const STORE = 'voice-reference';
  const KEY = 'active';
  let restoring = false;

  function openDB() {
    return new Promise((resolve, reject) => {
      if (!window.indexedDB) return reject(new Error('IndexedDB unavailable'));
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE);
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error || new Error('IndexedDB open failed'));
    });
  }

  async function putReference(file) {
    if (!file) return false;
    try {
      const db = await openDB();
      await new Promise((resolve, reject) => {
        const tx = db.transaction(STORE, 'readwrite');
        tx.objectStore(STORE).put({ blob: file, name: file.name || 'voice-reference', type: file.type || 'audio/wav', savedAt: Date.now() }, KEY);
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error || new Error('IndexedDB write failed'));
      });
      db.close();
      return true;
    } catch (_) {
      return false;
    }
  }

  async function getReference() {
    try {
      const db = await openDB();
      const value = await new Promise((resolve, reject) => {
        const tx = db.transaction(STORE, 'readonly');
        const req = tx.objectStore(STORE).get(KEY);
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => reject(req.error);
      });
      db.close();
      return value;
    } catch (_) {
      return null;
    }
  }

  async function restoreReference() {
    if (restoring) return false;
    const saved = await getReference();
    if (!saved?.blob) return false;

    restoring = true;
    try {
      const file = saved.blob instanceof File
        ? saved.blob
        : new File([saved.blob], saved.name || 'audiolab-voice-reference.wav', {
            type: saved.type || saved.blob.type || 'audio/wav'
          });

      // Go to Voices first so the real application's upload handler exists.
      const originalNav = window.__audiolabOriginalNav || window.nav;
      originalNav?.('voices');

      await new Promise(resolve => setTimeout(resolve, 180));
      const input = document.getElementById('voiceFile');
      if (!input) return false;

      const dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
      input.dispatchEvent(new Event('change', { bubbles: true }));

      // handleReference() assigns state.reference synchronously before analysis.
      await new Promise(resolve => setTimeout(resolve, 250));
      window.__audiolabVoiceHydrated = true;
      return true;
    } catch (_) {
      return false;
    } finally {
      restoring = false;
    }
  }

  // Capture every normal file upload and persist the real audio bytes locally.
  document.addEventListener('change', async event => {
    const input = event.target;
    if (input?.id !== 'voiceFile' || !input.files?.[0]) return;
    const file = input.files[0];
    const ok = await putReference(file);
    window.__audiolabVoiceHydrated = true;
    if (!ok) {
      const toast = document.getElementById('toast');
      if (toast) {
        toast.textContent = 'Voice selected. Browser storage was unavailable; keep this tab open for generation.';
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 2800);
      }
    }
  }, true);

  // Keep the original navigation function so restoration can bypass this wrapper.
  const originalNav = window.nav;
  if (typeof originalNav === 'function') {
    window.__audiolabOriginalNav = originalNav;
    window.nav = async function(page) {
      if (page === 'generate' && !window.__audiolabVoiceHydrated) {
        const restored = await restoreReference();
        if (!restored) {
          originalNav('generate');
          return;
        }
      }
      return originalNav(page);
    };
  }

  // Restore automatically on startup if a reference was saved previously.
  // This makes the voice survive refreshes and page navigation without a server/database.
  setTimeout(() => {
    restoreReference().catch(() => {});
  }, 350);
})();

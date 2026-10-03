(() => {
  const DB_NAME = 'audiolab-local';
  const STORE = 'voice-reference';
  const KEY = 'active';

  function openDB() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE);
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async function putReference(file) {
    try {
      const db = await openDB();
      await new Promise((resolve, reject) => {
        const tx = db.transaction(STORE, 'readwrite');
        tx.objectStore(STORE).put({ blob: file, name: file.name, type: file.type }, KEY);
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error);
      });
      db.close();
    } catch (_) {}
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

  async function hydrateReference() {
    if (window.__audiolabVoiceHydrated) return;
    const saved = await getReference();
    if (!saved?.blob) return;

    // The original Audiolab app keeps the active File in an in-memory state.
    // Recreate that File after a refresh by using the app's existing upload path.
    window.nav?.('voices');
    setTimeout(() => {
      const input = document.getElementById('voiceFile');
      if (!input) return;
      try {
        const file = new File([saved.blob], saved.name || 'audiolab-voice-reference', {
          type: saved.type || saved.blob.type || 'audio/wav'
        });
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;
        input.dispatchEvent(new Event('change', { bubbles: true }));
        window.__audiolabVoiceHydrated = true;
        setTimeout(() => window.nav?.('generate'), 120);
      } catch (_) {
        window.nav?.('generate');
      }
    }, 60);
  }

  // Capture the actual audio selected by the user before the app moves to Generate.
  document.addEventListener('change', event => {
    const input = event.target;
    if (input?.id === 'voiceFile' && input.files?.[0]) {
      window.__audiolabVoiceHydrated = true;
      putReference(input.files[0]);
    }
  }, true);

  const originalNav = window.nav;
  if (typeof originalNav === 'function') {
    window.nav = function(page) {
      if (page === 'generate' && !window.__audiolabVoiceHydrated) {
        hydrateReference();
        return;
      }
      return originalNav(page);
    };
  }
})();

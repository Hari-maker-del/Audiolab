(() => {
  const start = () => {
    try {
      if (typeof window.render === 'function') {
        window.render();
        return;
      }
      const studio = document.getElementById('page-studio');
      if (studio && !studio.innerHTML.trim()) {
        studio.innerHTML = '<div class="hero"><div><div class="eyebrow">Audiolab / Studio</div><h1>Create speech that sounds like you.</h1><p>Your voice. Your language. Your sound. A local-first Indian-language AI audio workspace.</p><div class="actions"><button class="btn primary" onclick="nav(\'generate\')">Create Voice</button><button class="btn secondary" onclick="nav(\'voices\')">Upload Reference</button></div></div></div>';
      }
    } catch (error) {
      console.error('Audiolab boot error:', error);
    }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();

/* Audiolab local-first API bridge.
   On localhost, the Vercel-style /api/* calls are forwarded to the local FastAPI server.
   Production hosts keep their existing routing untouched.
*/
(function () {
  const isLocal = ['localhost', '127.0.0.1'].includes(window.location.hostname);
  if (!isLocal) return;

  const LOCAL_API = 'http://127.0.0.1:8000';
  const originalFetch = window.fetch.bind(window);

  window.fetch = function (input, init) {
    let url = typeof input === 'string' ? input : input?.url;
    if (url && url.startsWith('/api/')) {
      const target = LOCAL_API + url.slice('/api'.length);
      if (typeof input === 'string') return originalFetch(target, init);
      return originalFetch(new Request(target, input), init);
    }
    return originalFetch(input, init);
  };

  window.AUDIOLAB_LOCAL_API = LOCAL_API;
  console.info('Audiolab local backend:', LOCAL_API);
})();

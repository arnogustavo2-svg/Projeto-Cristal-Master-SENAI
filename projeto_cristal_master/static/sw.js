const CACHE_NAME = 'cristal-master-v2';
const APP_SHELL = [
  '/static/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const { request } = event;

  // Nunca intercepta POST (registro de baixas/bloqueios) — precisa sempre ir à rede.
  if (request.method !== 'GET') return;

  if (request.mode === 'navigate') {
    // Network-first: dados de estoque/OP mudam a cada baixa e nunca podem ficar desatualizados
    // enquanto houver conexão. Cache só é usado como último recurso, offline.
    event.respondWith(
      fetch(request)
        .then(response => {
          const copia = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, copia));
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // Recursos estáticos (manifest, etc.): cache-first.
  event.respondWith(
    caches.match(request).then(response => response || fetch(request))
  );
});
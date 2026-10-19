// Cabinet Clear service worker.
// Network first: a new deploy shows up right away. The saved copy of /app is only used when offline.
const CACHE_NAME = 'cabinet-clear-v2';
const STATIC_ASSETS = ['/app'];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS)));
});

self.addEventListener('activate', event => {
  // delete the old v1 copy so nobody is stuck on an old version
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;                 // never touch API calls (POST)
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;       // leave other sites alone
  if (url.pathname.startsWith('/history')) return;  // history must always be live

  event.respondWith(
    fetch(req)
      .then(res => {
        if (res.ok && url.pathname === '/app') {
          const copy = res.clone();
          caches.open(CACHE_NAME).then(c => c.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req))
  );
});

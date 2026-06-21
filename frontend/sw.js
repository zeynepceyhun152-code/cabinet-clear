const CACHE_NAME = 'cabinet-clear-v1';
const STATIC_ASSETS = ['/app'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
});

self.addEventListener('fetch', event => {
  // Only cache GET requests for static assets, not API calls
  if (event.request.method !== 'GET' || event.request.url.includes('/extract') || 
      event.request.url.includes('/scan') || event.request.url.includes('/analyze') ||
      event.request.url.includes('/check') || event.request.url.includes('/generate')) {
    return;
  }
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});

const CACHE_NAME = "chesifa-shell-v1";
const SHELL_FILES = [
  "/che-si-fa-cerignola/",
  "/che-si-fa-cerignola/index.html",
  "/che-si-fa-cerignola/manifest.json",
  "/che-si-fa-cerignola/icon-192.png",
  "/che-si-fa-cerignola/icon-512.png"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL_FILES))
  );
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);

  if (url.pathname.endsWith("eventi.json")) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request))
  );
});

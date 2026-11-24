const CACHE_NAME = "chesifa-shell-v11";
const BASE_PATH = new URL(self.registration.scope).pathname;
const SHELL_FILES = [
  new URL("", self.registration.scope).href,
  new URL("index.html", self.registration.scope).href,
  new URL("manifest.json", self.registration.scope).href,
  new URL("1795175413227~4.jpg", self.registration.scope).href
];

function cacheKeyFor(request) {
  const url = new URL(request.url);
  // Il frontend aggiunge un timestamp a eventi.json: usa una chiave stabile
  // per non creare una voce di cache nuova a ogni visita.
  if ([`${BASE_PATH}eventi.json`, `${BASE_PATH}esperienze.json`].includes(url.pathname)) {
    url.search = "";
    url.hash = "";
  }
  return new Request(url.toString(), { method: "GET" });
}

async function salvaInCache(cache, key, response) {
  if (response && response.ok && response.type !== "opaque") {
    try {
      await cache.put(key, response.clone());
    } catch (error) {
      // Un problema di storage non deve bloccare la visualizzazione della risposta.
      console.warn("Cache non aggiornata:", error);
    }
  }
  return response;
}

async function retePrima(request, key) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      await salvaInCache(cache, key, response);
      return response;
    }
    const precedente = await cache.match(key);
    return precedente || response;
  } catch (error) {
    const precedente = await cache.match(key);
    if (precedente) return precedente;
    throw error;
  }
}

async function cachePrima(request, key) {
  const cache = await caches.open(CACHE_NAME);
  const precedente = await cache.match(key);
  const aggiornamento = fetch(request)
    .then(response => salvaInCache(cache, key, response))
    .catch(() => null);

  // Per le risorse statiche privilegia la risposta già disponibile e aggiorna
  // la cache in background; al primo accesso usa la rete.
  return precedente || await aggiornamento || new Response("Risorsa non disponibile", {
    status: 503,
    statusText: "Service Unavailable"
  });
}

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL_FILES))
  );
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(key => key.startsWith("chesifa-shell-") && key !== CACHE_NAME)
          .map(key => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("notificationclick", event => {
  event.notification.close();
  const destinazione = event.notification.data && event.notification.data.url
    ? event.notification.data.url
    : new URL("index.html", self.registration.scope).href;
  event.waitUntil((async () => {
    const finestre = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const finestra of finestre) {
      if (finestra.url.startsWith(self.registration.scope) && "focus" in finestra) {
        await finestra.focus();
        return;
      }
    }
    if (self.clients.openWindow) await self.clients.openWindow(destinazione);
  })());
});

self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  // Non intercettare Firebase, Analytics, font, immagini o altri servizi esterni.
  if (url.origin !== self.location.origin || !url.pathname.startsWith(BASE_PATH)) return;

  const key = cacheKeyFor(request);
  const isData = [`${BASE_PATH}eventi.json`, `${BASE_PATH}esperienze.json`].includes(url.pathname);
  const isPage = request.mode === "navigate" || url.pathname.endsWith(".html") || url.pathname === BASE_PATH;

  event.respondWith(
    isData || isPage
      ? retePrima(request, key)
      : cachePrima(request, key)
  );
});

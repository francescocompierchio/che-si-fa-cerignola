const CACHE_NAME = "chesifa-shell-v73";
const BASE_PATH = new URL(self.registration.scope).pathname;
const SHELL_FILES = [
  new URL("", self.registration.scope).href,
  new URL("index.html", self.registration.scope).href,
  new URL("manifest.json", self.registration.scope).href,
  new URL("event-tools.js", self.registration.scope).href,
  new URL("event-tools.js?v=44", self.registration.scope).href,
  new URL("metrics.js", self.registration.scope).href,
  new URL("metrics.js?v=34", self.registration.scope).href,
  new URL("public-views.js", self.registration.scope).href,
  new URL("public-views.js?v=31", self.registration.scope).href,
  new URL("event-page.js", self.registration.scope).href,
  new URL("event-page.js?v=69", self.registration.scope).href,
  new URL("app-extras.js", self.registration.scope).href,
  new URL("app-extras.js?v=3", self.registration.scope).href,
  new URL("side-panels.js?v=4", self.registration.scope).href,
  new URL("quick-report.js?v=1", self.registration.scope).href,
  new URL("1795175413227~4.jpg", self.registration.scope).href
];

function cacheKeyFor(request) {
  const url = new URL(request.url);
  // Il frontend aggiunge un timestamp a eventi.json: usa una chiave stabile
  // per non creare una voce di cache nuova a ogni visita.
  if ([`${BASE_PATH}eventi.json`, `${BASE_PATH}esperienze.json`, `${BASE_PATH}sitemap.xml`].includes(url.pathname)) {
    url.search = "";
    url.hash = "";
  }
  // I parametri di attribuzione non cambiano il contenuto della pagina.
  // Conserva invece parametri funzionali (per esempio admin o escludi).
  for(const p of ["utm_source","utm_medium","utm_campaign","utm_term","utm_content"])url.searchParams.delete(p);
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

function isHomeRequest(request) {
  const path=new URL(request.url).pathname;
  return path===BASE_PATH||path===BASE_PATH+"index.html";
}
async function paginaSalvata(cache,key,request){
  const exact=await cache.match(key);
  if(exact||!isHomeRequest(request))return exact;
  return (await cache.match(new URL("index.html",self.registration.scope).href)) ||
    (await cache.match(new URL("",self.registration.scope).href));
}
async function retePrima(request, key) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      await salvaInCache(cache, key, response);
      return response;
    }
    // Un evento rimosso dal sito non deve riapparire dalla cache.
    if (response && (response.status === 404 || response.status === 410) && !isHomeRequest(request)) { await cache.delete(key); return response; }
    const precedente = await paginaSalvata(cache,key,request);
    return precedente || response;
  } catch (error) {
    const precedente = await paginaSalvata(cache,key,request);
    if (precedente) return precedente;
    throw error;
  }
}

async function cachePrima(request, key, event) {
  const cache = await caches.open(CACHE_NAME);
  const precedente = await paginaSalvata(cache,key,request);
  const aggiornamento = fetch(request)
    .then(response => salvaInCache(cache, key, response))
    .catch(() => null);
  // Il fetch di aggiornamento viene mantenuto in vita dal worker.
  if(precedente)event.waitUntil(aggiornamento);

  // Per le risorse statiche privilegia la risposta già disponibile e aggiorna
  // la cache in background; al primo accesso usa la rete.
  return precedente || await aggiornamento || new Response("Risorsa non disponibile", {
    status: 503,
    statusText: "Service Unavailable"
  });
}

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(async cache => {
      await cache.addAll(SHELL_FILES.slice(0,2));
      await Promise.allSettled(SHELL_FILES.slice(2).map(url=>cache.add(url)));
    })
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

const SHARE_CACHE = "chesifa-social-local-v1";
const SHARE_MAX = 8 * 1024 * 1024;
const SHARE_TTL = 30 * 60 * 1000;

async function riceviCondivisione(request) {
  const home = new URL("index.html", self.registration.scope);
  home.searchParams.set("segnalaSocial", "1");
  try {
    const type = request.headers.get("content-type") || "";
    if (!/^multipart\/form-data;/i.test(type) || !request.body) return Response.redirect(home, 303);
    const reader = request.body.getReader();
    const chunks = [];
    let size = 0;
    for (;;) {
      const {done, value} = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > SHARE_MAX + 64 * 1024) {
        await reader.cancel();
        return Response.redirect(home, 303);
      }
      chunks.push(value);
    }
    const input = await new Response(new Blob(chunks), {headers:{"Content-Type":type}}).formData();
    const draft = new FormData();
    for (const [field, limit] of [["titolo",150],["testo",10000],["fonte",1800]]) {
      const value = input.get(field);
      if (typeof value === "string" && value.trim()) draft.set(field, value.trim().slice(0, limit));
    }
    const image = input.get("foto");
    if (image instanceof Blob && image.size > 0 && image.size <= SHARE_MAX &&
        ["image/jpeg", "image/png", "image/webp"].includes(image.type)) {
      draft.set("foto", image, "locandina."+({"image/jpeg":"jpg","image/png":"png","image/webp":"webp"}[image.type]));
    }
    if ([...draft.keys()].length === 0) return Response.redirect(home, 303);
    const cache = await caches.open(SHARE_CACHE);
    const now = Date.now();
    const keys = await cache.keys();
    await Promise.all(keys.slice(0, Math.max(0,keys.length-2)).map(key=>cache.delete(key)));
    for (const key of keys.slice(-2)) {
      const ts = Number(new URL(key.url).searchParams.get("t"));
      if (!ts || now-ts > SHARE_TTL) await cache.delete(key);
    }
    const id = crypto.randomUUID();
    const key = new URL("__bozza-social/"+id+"?t="+now, self.registration.scope);
    await cache.put(key, new Response(draft));
    home.searchParams.set("bozza", id);
    home.searchParams.set("t", String(now));
  } catch (_) {
    // Il modulo manuale rimane disponibile anche con memoria locale esaurita.
  }
  return Response.redirect(home, 303);
}

self.addEventListener("fetch", event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method === "POST" && request.mode === "navigate" && url.origin === self.location.origin &&
      url.pathname === BASE_PATH+"index.html" && url.search === "?ricevi-social=1") {
    event.respondWith(riceviCondivisione(request));
    return;
  }
  if (request.method !== "GET") return;
  // Non intercettare Firebase, Analytics, font, immagini o altri servizi esterni.
  if (url.origin !== self.location.origin || !url.pathname.startsWith(BASE_PATH)) return;
  // L'APK è un download separato: non occupare inutilmente la cache della PWA.
  if(/\.(apk|mp3)$/i.test(url.pathname)||request.headers.has("range"))return;

  const key = cacheKeyFor(request);
  const isData = [`${BASE_PATH}eventi.json`, `${BASE_PATH}esperienze.json`, `${BASE_PATH}sitemap.xml`].includes(url.pathname);
  const isPage = request.mode === "navigate" || url.pathname.endsWith(".html") || url.pathname === BASE_PATH;

  // I contatori devono usare codice coerente con la pagina appena pubblicata.
  const isMetrics = [`${BASE_PATH}metrics.js`, `${BASE_PATH}public-views.js`, `${BASE_PATH}event-page.js`].includes(url.pathname);
  event.respondWith(
    isData || isPage || isMetrics
      ? retePrima(request, key)
      : cachePrima(request, key, event)
  );
});

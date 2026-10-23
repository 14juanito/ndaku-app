/* Ndaku — service worker : application consultable hors connexion (favoris).
   - coquille (HTML/CSS/JS/polices) : réseau d'abord, copie de secours ;
   - données personnelles (session, favoris, fiches des favoris) : réseau d'abord, effacées à la déconnexion ;
   - photos : cache d'abord (les noms de fichiers sont uniques et immuables). */
const SHELL = "ndaku-shell-v5", DATA = "ndaku-data-v5", MEDIA = "ndaku-media-v5";
const SHELL_FILES = ["/", "/style.css", "/app.js", "/logo.svg", "/favicon.svg", "/manifest.webmanifest",
  "/vendor/leaflet/leaflet.css", "/vendor/leaflet/leaflet.js", "/vendor/markercluster/MarkerCluster.css",
  "/vendor/markercluster/leaflet.markercluster.js", "/fonts/poppins-latin-400-normal.woff2", "/fonts/poppins-latin-600-normal.woff2"];
const DATA_PATHS = /^\/api\/(meta|auth\/me|auth\/config|favorites|favorites\/ids)$/;

self.addEventListener("install", e => { e.waitUntil(caches.open(SHELL).then(c => c.addAll(SHELL_FILES)).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => ![SHELL, DATA, MEDIA].includes(k)).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("message", e => {
  if (e.data === "clear") e.waitUntil(Promise.all([caches.delete(DATA), caches.delete(MEDIA)]));
});

async function networkFirst(req, cacheName, store = true) {
  try {
    const res = await fetch(req);
    if (store && res.ok) (await caches.open(cacheName)).put(req, res.clone());
    return res;
  } catch (err) {
    const hit = await caches.match(req, { cacheName, ignoreVary: true });
    if (hit) return hit;
    throw err;
  }
}

self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;
  const p = url.pathname;
  if (req.mode === "navigate") return e.respondWith(networkFirst(new Request("/"), SHELL).catch(() => caches.match("/")));
  if (DATA_PATHS.test(p) && !url.search) return e.respondWith(networkFirst(req, DATA));
  if (/^\/api\/listings\/\d+$/.test(p)) {
    // Seules les fiches préchargées pour les favoris sont conservées ; les autres servent de secours si déjà en cache.
    return e.respondWith(networkFirst(req, DATA, req.headers.get("X-Ndaku-Offline") === "1"));
  }
  if (p.startsWith("/media/")) {
    return e.respondWith(caches.open(MEDIA).then(async c => (await c.match(req)) || fetch(req).then(res => { if (res.ok) c.put(req, res.clone()); return res; })));
  }
  if (SHELL_FILES.includes(p) || p.startsWith("/fonts/") || p.startsWith("/vendor/")) return e.respondWith(networkFirst(req, SHELL));
});

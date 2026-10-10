// GoldenHour service worker: app-shell caching so the installed app opens even with
// no signal (critical for paramedics in low-coverage areas), while API/WS calls always
// go to the network — this app's data is live, not something to serve stale from cache.
const CACHE = "goldenhour-shell-v1";
const SHELL = [
  "/", "/patient", "/ambulance", "/hospital",
  "/manifest.webmanifest", "/ambulance/manifest.webmanifest", "/hospital/manifest.webmanifest",
  "/icons/icon-192.png", "/icons/icon-512.png", "/icons/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL).catch(() => {})).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // never cache API or websocket traffic: this data is live
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/core/") || url.pathname.startsWith("/ws")) return;

  // network-first for navigations, falling back to the cached shell when offline
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
          return res;
        })
        .catch(() => caches.match(req).then((r) => r ?? caches.match("/"))),
    );
    return;
  }

  // cache-first for static assets (icons, chunks, fonts)
  event.respondWith(
    caches.match(req).then((cached) => cached ?? fetch(req).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
      return res;
    }).catch(() => cached)),
  );
});

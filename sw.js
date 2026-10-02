// Offline support: app files load from cache; the brief is fetched fresh when online
// and falls back to the last copy saved here.
const CACHE = "black-brief-v2";
const SHELL = ["./", "index.html", "app.css", "app.js", "manifest.webmanifest", "icons/icon-192.png", "icons/icon-180.png", "tips.txt", "photos/photos.json"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;
  const fresh = url.pathname.endsWith("/data/latest.json") || req.mode === "navigate"
    || /\.(js|css)$/.test(url.pathname) || /(tips\.txt|photos\.json)$/.test(url.pathname);
  e.respondWith(fresh
    ? fetch(req).then((r) => { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); return r; })
        .catch(() => caches.match(req).then((m) => m || caches.match("index.html")))
    : caches.match(req).then((m) => m || fetch(req).then((r) => { // photos are saved as they're first seen
        if (r.ok) { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); }
        return r;
      })));
});

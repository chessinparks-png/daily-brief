// Offline support. The app files, tips and the brief are fetched fresh when online and
// saved here, so the last brief still opens offline. Park photos and icons are saved the
// first time they're shown. Card pictures come from other sites and aren't saved; offline,
// those cards fall back to their color gradient.
const CACHE = "black-brief-site-v1";
const SHELL = [
  "./", "index.html", "styles.css", "app.js", "manifest.webmanifest", "tips.txt", "parks/parks.json",
  "icons/icon-180.png", "icons/icon-192.png", "icons/icon-512.png", "icons/icon-maskable-512.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

const save = (req, r) => {
  if (r.ok) { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); }
  return r;
};

self.addEventListener("fetch", (e) => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;
  const fresh = req.mode === "navigate" || url.pathname.endsWith("/data/latest.json")
    || /\.(js|css|json|txt|webmanifest)$/.test(url.pathname);
  e.respondWith(fresh
    ? fetch(req).then((r) => save(req, r)).catch(() =>
        caches.match(req, { ignoreSearch: true })
          .then((m) => m || (req.mode === "navigate" ? caches.match("index.html") : Response.error())))
    : caches.match(req).then((m) => m || fetch(req).then((r) => save(req, r))));
});

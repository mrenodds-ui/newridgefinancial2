/* Offline read-only cache — Moonshot Phase 9 expanded */
const CACHE = "nr2-offline-v2";
const SHELL = ["/", "/index.html", "/styles.css", "/app.js", "/desktop-bridge.js", "/hal-transparency.js"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
});
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))),
  );
});
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/")) return;
  event.respondWith(
    fetch(event.request)
      .then((r) => {
        if (r && r.ok && url.origin === self.location.origin) {
          const copy = r.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return r;
      })
      .catch(() => caches.match(event.request).then((r) => r || caches.match("/index.html"))),
  );
});

const CACHE_NAME = "newridge-shell-v2";
const ADMIN_REFRESH_SYNC_TAG = "newridge-admin-refresh-retry";
const APP_SHELL = ["/", "/app/", "/app", "/admin", "/index.html", "/app/index.html", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(async () => {
        if (!self.registration.active) {
          return;
        }
        const windows = await self.clients.matchAll({ type: "window" });
        windows.forEach((client) => client.postMessage({ type: "UPDATE_AVAILABLE" }));
      }),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) return caches.delete(key);
          return Promise.resolve(true);
        })
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

self.addEventListener("sync", (event) => {
  if (event.tag !== ADMIN_REFRESH_SYNC_TAG) {
    return;
  }

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      windows.forEach((client) => {
        client.postMessage({ type: "SYNC_RETRY_ADMIN_REFRESH" });
      });
    }),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (url.pathname.startsWith("/api/")) {
    return;
  }
  if (request.method !== "GET") {
    return;
  }

  event.respondWith(
    fetch(request)
      .then((response) => {
        const copy = response.clone();
        void caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        return response;
      })
      .catch(async () => {
        const cached = await caches.match(request);
        if (cached) return cached;
        const shell = (await caches.match("/app/index.html")) ?? (await caches.match("/index.html"));
        if (shell) return shell;
        return new Response("Offline shell not available.", { status: 503, statusText: "Service Unavailable" });
      })
  );
});

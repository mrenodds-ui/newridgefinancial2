/* Offline read-only cache — Moonshot Phase 9; mock-embed uses network-first for versioned assets. */
const BUILD_ID = "hal-10496";
const CACHE = "nr2-offline-v14-apex";
const INTEGRITY = "nr2-offline-integrity-v2";
const SHELL = ["/", "/index.html"];

async function sha384Base64(buffer) {
  const hash = await crypto.subtle.digest("SHA-384", buffer);
  const bytes = new Uint8Array(hash);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function integrityKey(url) {
  return `${url}:sha384`;
}

async function putWithIntegrity(cache, request, response) {
  const buffer = await response.clone().arrayBuffer();
  const digest = await sha384Base64(buffer);
  await cache.put(request, new Response(buffer, { headers: response.headers }));
  const integrityCache = await caches.open(INTEGRITY);
  await integrityCache.put(integrityKey(request.url), new Response(digest));
}

async function precacheWithSRI(cache, url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response || !response.ok) {
    throw new Error(`Precache fetch failed: ${url} (${response ? response.status : "no response"})`);
  }
  await putWithIntegrity(cache, new Request(url), response);
}

async function matchWithIntegrity(request) {
  const cached = await caches.match(request);
  if (!cached) return null;
  const integrityCache = await caches.open(INTEGRITY);
  const digestResponse = await integrityCache.match(integrityKey(request.url));
  if (!digestResponse) return null;
  const expected = await digestResponse.text();
  const actual = await sha384Base64(await cached.clone().arrayBuffer());
  if (actual !== expected) return null;
  return cached;
}

function notifyOfflineStale() {
  self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
    clients.forEach((client) => client.postMessage({ type: "nr2-offline-stale" }));
  });
}

function isVersionedAppAsset(url) {
  if (url.origin !== self.location.origin) return false;
  if (url.searchParams.has("v")) return true;
  return /\.(js|css|html|json)$/i.test(url.pathname);
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE);
      for (const path of SHELL) {
        await precacheWithSRI(cache, path);
      }
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => key !== CACHE && key !== INTEGRITY).map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "NR2_KILL_LEGACY") {
    caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k))));
    self.skipWaiting();
  }
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  const paramBuild = url.searchParams.get("v");
  if (paramBuild && paramBuild !== BUILD_ID) {
    event.respondWith(fetch(event.request, { cache: "no-store" }));
    return;
  }
  if (url.pathname.startsWith("/api/")) return;
  if (isVersionedAppAsset(url)) {
    event.respondWith(
      fetch(event.request, { cache: "no-store" }).catch(async () => {
        const cached = await matchWithIntegrity(event.request);
        if (cached) notifyOfflineStale();
        return cached || Response.error();
      }),
    );
    return;
  }
  event.respondWith(
    fetch(event.request, { cache: "no-store" })
      .then((response) => {
        if (response && response.ok && url.origin === self.location.origin && !isVersionedAppAsset(url)) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => putWithIntegrity(cache, event.request, copy));
        }
        return response;
      })
      .catch(async () => {
        const cached = await matchWithIntegrity(event.request);
        if (cached) {
          notifyOfflineStale();
          return cached;
        }
        const fallback = await matchWithIntegrity(new Request("/index.html"));
        if (fallback) notifyOfflineStale();
        return fallback || caches.match("/index.html");
      }),
  );
});










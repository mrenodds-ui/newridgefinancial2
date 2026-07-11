/**
 * NR2 IndexedDB key-value store — browser client cache (no npm deps).
 * Used for Apex widget mosaics and DesktopBridge browser fallback.
 * PHI: do not store model transcripts / chat history here (session or SQLite only).
 */
(function (global) {
  "use strict";

  const DB_NAME = "nr2-apex";
  const DB_VERSION = 1;
  const STORE = "kv";
  const WIDGET_TTL_MS = 24 * 60 * 60 * 1000;

  /** Keys that must not land in durable browser storage (retention / PHI). */
  const SESSION_ONLY_KEY =
    /(chatHistory|ChatHistory|transcript|halEvidencePacket|halOperatorReport|narrative-draft)/i;

  let dbPromise = null;
  let available = null;

  function canUseIndexedDb() {
    if (available !== null) return available;
    try {
      available = typeof indexedDB !== "undefined" && indexedDB !== null;
    } catch (_err) {
      available = false;
    }
    return available;
  }

  function openDb() {
    if (!canUseIndexedDb()) return Promise.reject(new Error("indexedDB unavailable"));
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
      let req;
      try {
        req = indexedDB.open(DB_NAME, DB_VERSION);
      } catch (err) {
        available = false;
        reject(err);
        return;
      }
      req.onerror = () => {
        available = false;
        reject(req.error || new Error("indexedDB open failed"));
      };
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(STORE)) {
          db.createObjectStore(STORE);
        }
      };
      req.onsuccess = () => resolve(req.result);
    });
    return dbPromise;
  }

  function isSessionOnlyKey(key) {
    return SESSION_ONLY_KEY.test(String(key || ""));
  }

  function reqToPromise(req) {
    return new Promise((resolve, reject) => {
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error || new Error("indexedDB request failed"));
    });
  }

  async function withStore(mode, fn) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      const store = tx.objectStore(STORE);
      let req;
      try {
        req = fn(store);
      } catch (err) {
        reject(err);
        return;
      }
      const done = reqToPromise(req);
      tx.onabort = () => reject(tx.error || new Error("indexedDB aborted"));
      tx.onerror = () => reject(tx.error || new Error("indexedDB transaction failed"));
      done.then(resolve, reject);
    });
  }

  async function get(key) {
    if (!canUseIndexedDb()) return null;
    try {
      return await withStore("readonly", (store) => store.get(String(key)));
    } catch (_err) {
      return null;
    }
  }

  async function set(key, value) {
    if (!canUseIndexedDb()) return false;
    if (isSessionOnlyKey(key)) return false;
    try {
      await withStore("readwrite", (store) => store.put(value, String(key)));
      return true;
    } catch (_err) {
      return false;
    }
  }

  async function del(key) {
    if (!canUseIndexedDb()) return false;
    try {
      await withStore("readwrite", (store) => store.delete(String(key)));
      return true;
    } catch (_err) {
      return false;
    }
  }

  async function clear() {
    if (!canUseIndexedDb()) return false;
    try {
      await withStore("readwrite", (store) => store.clear());
      return true;
    } catch (_err) {
      return false;
    }
  }

  function widgetCacheKey(page, sub, query) {
    if (query && query.id) return null;
    const p = String(page || "financial");
    const s = sub ? String(sub) : "";
    return `widgets:${p}:${s}`;
  }

  async function cacheWidgets(page, sub, query, payload) {
    const key = widgetCacheKey(page, sub, query);
    if (!key || !payload) return false;
    return set(key, {
      cachedAt: new Date().toISOString(),
      page,
      sub: sub || null,
      payload,
    });
  }

  async function loadWidgets(page, sub, query) {
    const key = widgetCacheKey(page, sub, query);
    if (!key) return null;
    const entry = await get(key);
    if (!entry || !entry.payload) return null;
    const cachedAt = Date.parse(entry.cachedAt || "");
    if (Number.isFinite(cachedAt) && Date.now() - cachedAt > WIDGET_TTL_MS) {
      return null;
    }
    return entry;
  }

  const api = {
    DB_NAME,
    isAvailable: canUseIndexedDb,
    isSessionOnlyKey,
    get,
    set,
    del,
    clear,
    widgetCacheKey,
    cacheWidgets,
    loadWidgets,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  global.Nr2IndexedDb = api;
})(typeof window !== "undefined" ? window : globalThis);

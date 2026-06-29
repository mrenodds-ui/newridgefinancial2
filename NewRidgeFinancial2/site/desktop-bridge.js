/**
 * Desktop bridge — local file reads and SQLite-backed storage via pywebview.
 * Falls back to fetch + sessionStorage only for local file dev (no server).
 */
const DesktopBridge = (function () {
  function hasDesktopApi() {
    return Boolean(window.pywebview && window.pywebview.api);
  }

  function whenReady(callback) {
    if (hasDesktopApi()) {
      if (window.pywebview.api.get_app_info) {
        callback();
        return;
      }
      window.addEventListener("pywebviewready", () => callback(), { once: true });
      return;
    }
    callback();
  }

  async function readDataFile(name) {
    if (hasDesktopApi()) {
      const text = await window.pywebview.api.read_data_file(name);
      return JSON.parse(text);
    }
    const response = await fetch(`data/${name}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Data file unavailable: ${name}`);
    return response.json();
  }

  async function storageGet(key) {
    if (hasDesktopApi()) {
      const raw = await window.pywebview.api.storage_get(key);
      if (raw == null || raw === "") return null;
      try {
        return JSON.parse(raw);
      } catch {
        return null;
      }
    }
    try {
      const raw = sessionStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  async function storageSet(key, value) {
    const payload = JSON.stringify(value);
    if (hasDesktopApi()) {
      await window.pywebview.api.storage_set(key, payload);
      return;
    }
    try {
      sessionStorage.setItem(key, payload);
    } catch {
      /* storage may be unavailable */
    }
  }

  async function getAppInfo() {
    if (hasDesktopApi()) return window.pywebview.api.get_app_info();
    return { mode: "file", version: "2.0" };
  }

  async function getImportBundle() {
    if (hasDesktopApi() && window.pywebview.api.get_import_bundle) {
      return window.pywebview.api.get_import_bundle();
    }
    return null;
  }

  async function refreshImports() {
    if (hasDesktopApi() && window.pywebview.api.refresh_imports) {
      return window.pywebview.api.refresh_imports();
    }
    return getImportBundle();
  }

  return { hasDesktopApi, whenReady, readDataFile, storageGet, storageSet, getAppInfo, getImportBundle, refreshImports };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = DesktopBridge;
}
if (typeof window !== "undefined") {
  window.DesktopBridge = DesktopBridge;
}

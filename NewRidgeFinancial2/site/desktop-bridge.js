/**
 * Desktop bridge — local file reads and SQLite-backed storage via pywebview.
 * Falls back to fetch + sessionStorage only for local file dev (no server).
 */
const DesktopBridge = (function () {
  function hasDesktopApi() {
    if (typeof window === "undefined") return false;
    return Boolean(window.pywebview && window.pywebview.api);
  }

  function runtimeMode() {
    return hasDesktopApi() ? "desktop" : "browser-dev";
  }

  function desktopRequiredMessage(feature) {
    const label = feature || "This feature";
    return `${label} requires the NR2 desktop app. Browser/file mode is a UI preview only: imports, SQLite storage, SideNotes hub files, and import sync are unavailable. Launch with scripts/start_nr2_1966.ps1.`;
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
    if (typeof window === "undefined") {
      callback();
      return;
    }

    let called = false;
    const finish = () => {
      if (called) return;
      called = true;
      callback();
    };

    window.addEventListener("pywebviewready", finish, { once: true });
    window.setTimeout(finish, 1500);
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

  function parseStorageValue(raw) {
    if (raw == null || raw === "") return null;
    if (typeof raw === "object") return raw;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  async function storageGet(key) {
    if (hasDesktopApi()) {
      const raw = await window.pywebview.api.storage_get(key);
      return parseStorageValue(raw);
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

  async function getImportSyncStatus() {
    if (hasDesktopApi() && window.pywebview.api.get_import_sync_status) {
      return window.pywebview.api.get_import_sync_status();
    }
    return { status: "idle" };
  }

  async function refreshImports() {
    if (hasDesktopApi() && window.pywebview.api.refresh_imports) {
      return window.pywebview.api.refresh_imports();
    }
    return getImportBundle();
  }

  async function syncAccountingDocuments() {
    if (hasDesktopApi() && window.pywebview.api.sync_accounting_documents) {
      return window.pywebview.api.sync_accounting_documents();
    }
    return null;
  }

  async function listPracticeSourceCatalog() {
    if (hasDesktopApi() && window.pywebview.api.list_practice_source_catalog) {
      return window.pywebview.api.list_practice_source_catalog();
    }
    return null;
  }

  async function fetchPracticeSource(system, resource, options) {
    if (hasDesktopApi() && window.pywebview.api.fetch_practice_source) {
      const payload = options && typeof options === "object" ? JSON.stringify(options) : "{}";
      return window.pywebview.api.fetch_practice_source(system, resource, payload);
    }
    return null;
  }

  async function pullPracticeSources(options) {
    const opts = options && typeof options === "object" ? options : {};
    if (hasDesktopApi() && window.pywebview.api.pull_practice_sources) {
      return window.pywebview.api.pull_practice_sources(JSON.stringify(opts));
    }
    return null;
  }

  function isTextField(el) {
    if (!el || typeof el !== "object") return false;
    const tag = String(el.tagName || "").toUpperCase();
    if (tag === "TEXTAREA" || tag === "INPUT") {
      const type = String(el.type || "text").toLowerCase();
      return type !== "button" && type !== "submit" && type !== "checkbox" && type !== "radio" && type !== "file";
    }
    return Boolean(el.isContentEditable);
  }

  function selectedCopyText() {
    const selection = typeof window !== "undefined" && window.getSelection ? window.getSelection() : null;
    const selected = selection ? String(selection.toString() || "") : "";
    if (selected) return selected;
    const active = typeof document !== "undefined" ? document.activeElement : null;
    if (!isTextField(active)) return "";
    const start = active.selectionStart;
    const end = active.selectionEnd;
    if (start == null || end == null || start === end) return "";
    return String(active.value || "").slice(start, end);
  }

  function insertAtCursor(el, text) {
    if (!el || text == null) return;
    const payload = String(text);
    if (el.tagName === "TEXTAREA" || el.tagName === "INPUT") {
      const start = el.selectionStart == null ? el.value.length : el.selectionStart;
      const end = el.selectionEnd == null ? el.value.length : el.selectionEnd;
      const before = String(el.value || "").slice(0, start);
      const after = String(el.value || "").slice(end);
      el.value = before + payload + after;
      const pos = start + payload.length;
      el.selectionStart = pos;
      el.selectionEnd = pos;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }
    if (el.isContentEditable && typeof document !== "undefined" && document.execCommand) {
      document.execCommand("insertText", false, payload);
    }
  }

  async function readClipboard() {
    if (hasDesktopApi() && window.pywebview.api.clipboard_read) {
      return String((await window.pywebview.api.clipboard_read()) || "");
    }
    if (typeof navigator !== "undefined" && navigator.clipboard && navigator.clipboard.readText) {
      return String((await navigator.clipboard.readText()) || "");
    }
    return "";
  }

  async function writeClipboard(text) {
    const payload = text == null ? "" : String(text);
    if (!payload) return false;
    if (hasDesktopApi() && window.pywebview.api.clipboard_write) {
      return Boolean(await window.pywebview.api.clipboard_write(payload));
    }
    if (typeof navigator !== "undefined" && navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(payload);
      return true;
    }
    if (typeof document !== "undefined") {
      const area = document.createElement("textarea");
      area.value = payload;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.left = "-9999px";
      document.body.appendChild(area);
      area.select();
      let ok = false;
      try {
        ok = document.execCommand("copy");
      } catch {
        ok = false;
      }
      document.body.removeChild(area);
      return ok;
    }
    return false;
  }

  let clipboardHandlersInstalled = false;

  function installClipboardHandlers() {
    if (clipboardHandlersInstalled || typeof document === "undefined") return;
    clipboardHandlersInstalled = true;

    if (hasDesktopApi() && document.body) {
      document.body.classList.add("nr2-desktop");
    }

    document.addEventListener(
      "copy",
      (event) => {
        if (!hasDesktopApi()) return;
        const text = selectedCopyText();
        if (!text) return;
        event.preventDefault();
        writeClipboard(text).catch(() => {
          /* clipboard optional */
        });
      },
      true,
    );

    document.addEventListener(
      "paste",
      (event) => {
        if (!hasDesktopApi()) return;
        const target = event.target;
        if (!isTextField(target)) return;
        event.preventDefault();
        readClipboard()
          .then((text) => {
            if (text) insertAtCursor(target, text);
          })
          .catch(() => {
            /* clipboard optional */
          });
      },
      true,
    );

    document.addEventListener(
      "keydown",
      (event) => {
        if (!hasDesktopApi()) return;
        if (!(event.ctrlKey || event.metaKey)) return;
        const key = String(event.key || "").toLowerCase();
        if (key === "c") {
          const text = selectedCopyText();
          if (!text) return;
          event.preventDefault();
          writeClipboard(text).catch(() => {
            /* clipboard optional */
          });
          return;
        }
        if (key === "v") {
          const target = document.activeElement;
          if (!isTextField(target)) return;
          event.preventDefault();
          readClipboard()
            .then((text) => {
              if (text) insertAtCursor(target, text);
            })
            .catch(() => {
              /* clipboard optional */
            });
          return;
        }
        if (key === "x") {
          const target = document.activeElement;
          if (!isTextField(target)) return;
          const start = target.selectionStart;
          const end = target.selectionEnd;
          if (start == null || end == null || start === end) return;
          const snippet = String(target.value || "").slice(start, end);
          if (!snippet) return;
          event.preventDefault();
          writeClipboard(snippet)
            .then(() => {
              const before = String(target.value || "").slice(0, start);
              const after = String(target.value || "").slice(end);
              target.value = before + after;
              target.selectionStart = start;
              target.selectionEnd = start;
              target.dispatchEvent(new Event("input", { bubbles: true }));
            })
            .catch(() => {
              /* clipboard optional */
            });
        }
      },
      true,
    );
  }

  return {
    hasDesktopApi,
    runtimeMode,
    desktopRequiredMessage,
    whenReady,
    readDataFile,
    storageGet,
    storageSet,
    getAppInfo,
    getImportBundle,
    getImportSyncStatus,
    refreshImports,
    syncAccountingDocuments,
    listPracticeSourceCatalog,
    fetchPracticeSource,
    pullPracticeSources,
    readClipboard,
    writeClipboard,
    installClipboardHandlers,
    isTextField,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = DesktopBridge;
}
if (typeof window !== "undefined") {
  window.DesktopBridge = DesktopBridge;
}

/**
 * Desktop boot gate — verify schema shell loaded and all assets share one build version.
 * Runs after moonshot-page-registry.js + mockup chrome, before app.js.
 * Moonshot must-fix: verifyBuildConsensus + renderReloadUX (build consensus gate).
 * Moonshot stale-schema: emergencyPurgeAndReload + epoch manifest gate.
 */
(function () {
  const REQUIRED_BUILD = "hal-10139";
  const REQUIRED_EPOCH = "moonshot-mockup";
  const errors = [];

  function isWorkstationApp() {
    if (typeof window !== "undefined" && window.NR2_FINANCIAL_ONLY) return false;
    return Boolean(
      (typeof window !== "undefined" && window.NR2_WORKSTATION_ONLY) ||
        (typeof WorkstationSchema !== "undefined" && typeof PageSchema === "undefined"),
    );
  }

  function safeSchemaVersion() {
    if (typeof WorkstationSchema !== "undefined" && WorkstationSchema.SCHEMA_VERSION) {
      return String(WorkstationSchema.SCHEMA_VERSION);
    }
    if (typeof PageSchema !== "undefined" && PageSchema.SCHEMA_VERSION) {
      return String(PageSchema.SCHEMA_VERSION);
    }
    return null;
  }

  function reloadTargetUrl() {
    if (isWorkstationApp()) {
      return "/workstation/index.html?v=" + REQUIRED_BUILD + "&__nr2_purge=" + Date.now();
    }
    const base = location.pathname === "/workstation/index.html" ? "/" : location.pathname || "/";
    return base + "?v=" + REQUIRED_BUILD + "&__nr2_purge=" + Date.now() + location.hash;
  }

  function emergencyPurgeAndReload(reason) {
    console.error("[NR2] EMERGENCY PURGE:", reason);
    if ("caches" in window) {
      caches.keys().then((ks) => Promise.all(ks.map((k) => caches.delete(k)))).catch(() => {});
    }
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker
        .getRegistrations()
        .then((regs) => Promise.all(regs.map((r) => r.unregister())))
        .finally(() => {
          location.href = reloadTargetUrl();
        });
    } else {
      location.href = reloadTargetUrl();
    }
  }

  function assertMockupShell() {
    if (isWorkstationApp()) return true;
    if (!window.PageSchema || PageSchema.LAYOUT_EPOCH !== "moonshot-mockup") {
      emergencyPurgeAndReload("SCHEMA_EPOCH stale");
      return false;
    }
    const sidebar = document.getElementById("sidebar");
    if (sidebar && (sidebar.querySelector(".nav-group") || sidebar.querySelector(".brand--canvas"))) {
      emergencyPurgeAndReload("LEGACY_SIDEBAR");
      return false;
    }
    return true;
  }

  async function verifyBuildConsensusManifest() {
    try {
      const res = await fetch("/nr2-build.json?v=" + Date.now(), { cache: "no-store" });
      const json = await res.json();
      if (json.BUILD_ID !== REQUIRED_BUILD) throw new Error("BUILD_ID mismatch");
      if (!isWorkstationApp()) {
        if (window.PageSchema && window.PageSchema.LAYOUT_EPOCH !== REQUIRED_EPOCH) {
          throw new Error("SCHEMA_EPOCH stale");
        }
      } else if (typeof WorkstationSchema !== "undefined" && WorkstationSchema.SCHEMA_VERSION !== REQUIRED_BUILD) {
        throw new Error("Workstation schema version mismatch");
      }
      return true;
    } catch (e) {
      if (isWorkstationApp()) {
        console.warn("[NR2 Boot] Workstation manifest check skipped:", e.message);
        return false;
      }
      emergencyPurgeAndReload(e.message);
      return false;
    }
  }

  function readScriptAssetVersions() {
    const versions = new Set();
    document.querySelectorAll('script[src*=".js"]').forEach((node) => {
      const src = node.getAttribute("src") || "";
      if (!src || src.startsWith("http")) return;
      const match = src.match(/[?&]v=([^&]+)/);
      if (match) versions.add(match[1]);
    });
    return versions;
  }

  function htmlAssetVersion() {
    const meta = document.querySelector('meta[name="nr2-asset-version"]');
    if (meta && meta.getAttribute("content")) return String(meta.getAttribute("content")).trim();
    const versions = readScriptAssetVersions();
    return versions.size === 1 ? Array.from(versions)[0] : null;
  }

  function expectedSchemaVersion() {
    if (typeof WorkstationSchema !== "undefined" && WorkstationSchema.SCHEMA_VERSION) {
      return String(WorkstationSchema.SCHEMA_VERSION);
    }
    if (typeof PageSchema !== "undefined" && PageSchema.SCHEMA_VERSION) {
      return String(PageSchema.SCHEMA_VERSION);
    }
    return null;
  }

  function verifyBuildConsensus(expectedBuild) {
    const scripts = Array.from(document.querySelectorAll("script[src]"));
    const mismatches = [];
    for (const s of scripts) {
      const src = s.getAttribute("src") || "";
      const v = new URL(src, location.href).searchParams.get("v") || s.dataset.nr2Build;
      if (v && v !== expectedBuild) mismatches.push(src.split("?")[0]);
    }
    const schemaVer = safeSchemaVersion();
    if (schemaVer && String(schemaVer) !== expectedBuild) mismatches.push(`schema:${schemaVer}`);

    if (mismatches.length) {
      console.error("[NR2 Boot] Consensus failure:", mismatches);
      renderReloadUX(expectedBuild, mismatches);
      throw new Error(`Build consensus failed for ${expectedBuild}`);
    }
  }

  function renderReloadUX(build, mismatches) {
    document.body.innerHTML =
      `<div id="nr2-boot-reload" style="font-family:system-ui,sans-serif;max-width:480px;margin:10vh auto;padding:2rem;text-align:center;border:1px solid #ddd;border-radius:8px;">` +
      `<h2 style="margin-top:0;color:#c00;">NewRidge Financial Update Required</h2>` +
      `<p>Your browser cached mixed versions of the application (<code>${String(build).replace(/</g, "&lt;")}</code>).</p>` +
      `<p style="color:#666;font-size:0.95rem;">Affected: ${mismatches
        .slice(0, 3)
        .map((m) => String(m).replace(/</g, "&lt;"))
        .join(", ")}${mismatches.length > 3 ? "…" : ""}</p>` +
      `<button type="button" onclick="location.reload(true)" style="padding:0.6rem 1.2rem;font-size:1rem;cursor:pointer;">Reload Application</button>` +
      `<p style="font-size:0.85rem;color:#888;margin-top:1rem;">If this repeats, close all NR2 tabs and reopen, or press Ctrl+F5.</p>` +
      `</div>`;
  }

  function tryRecoverStaleCache(targetVersion) {
    if (!targetVersion) return false;
    const reloadKey = `nr2CacheRecover:${targetVersion}`;
    if (sessionStorage.getItem(reloadKey)) return false;
    sessionStorage.setItem(reloadKey, "1");
    try {
      if (typeof caches !== "undefined") {
        caches.keys().then((keys) => Promise.all(keys.map((key) => caches.delete(key)))).catch(() => {});
      }
      if (typeof navigator !== "undefined" && navigator.serviceWorker && navigator.serviceWorker.getRegistrations) {
        navigator.serviceWorker.getRegistrations().then((regs) => regs.forEach((reg) => reg.unregister())).catch(() => {});
      }
    } catch {
      /* cache cleanup optional */
    }
    const url = new URL(window.location.href);
    url.searchParams.set("v", targetVersion);
    window.location.replace(url.toString());
    return true;
  }

  function renderBootFailure(message, details) {
    const frame = document.getElementById("pageFrame");
    const sidebar = document.getElementById("sidebar");
    if (sidebar) {
      sidebar.innerHTML =
        '<div class="sidebar__boot-error"><strong>NR2 boot failed</strong><p>Restart Start Program.</p></div>';
    }
    if (!frame) return;
    const detailHtml = (details || [])
      .map((line) => `<li>${String(line).replace(/</g, "&lt;")}</li>`)
      .join("");
    const inner =
      `<strong class="ms-boot-error__title">${String(message).replace(/</g, "&lt;")}</strong>` +
      (detailHtml ? `<ul class="ms-boot-error__list">${detailHtml}</ul>` : "") +
      `<p class="ms-boot-error__msg">Close the window and launch <strong>${typeof WorkstationSchema !== "undefined" ? "Start Workstation" : "Start Program"}</strong> again. If this persists, clear site data for 127.0.0.1:8765 and run scripts/Refresh-NR2-DesktopShortcut.ps1.</p>`;
    if (typeof WorkstationSchema !== "undefined" && frame.querySelector("#workstationPage")) {
      let banner = frame.querySelector(".nr2-boot-error");
      if (!banner) {
        banner = document.createElement("div");
        banner.className = "ms-boot-error nr2-boot-error ws-boot-error";
        banner.setAttribute("role", "alert");
        frame.insertBefore(banner, frame.firstChild);
      }
      banner.innerHTML = inner;
      return;
    }
    frame.innerHTML = `<div class="ms-boot-error nr2-boot-error" role="alert">${inner}</div>`;
  }

  const schemaVersion = expectedSchemaVersion();
  const htmlVersion = htmlAssetVersion();
  const expectedBuild =
    schemaVersion ||
    document.documentElement.dataset.nr2Build ||
    htmlVersion ||
    null;

  if (!schemaVersion && !isWorkstationApp()) {
    errors.push("moonshot-page-registry.js did not define PageSchema.SCHEMA_VERSION.");
  }
  if (typeof MoonshotMockupChrome === "undefined") {
    errors.push("nr2-moonshot-mockup-chrome.js failed to load (MoonshotMockupChrome is undefined).");
  }
  if (typeof PageSchema === "undefined" || typeof PageSchema.navPages !== "function") {
    if (typeof WorkstationSchema === "undefined") {
      errors.push("moonshot-page-registry.js failed to load (PageSchema.navPages missing).");
    }
  }

  if (expectedBuild) {
    try {
      verifyBuildConsensus(expectedBuild);
    } catch (consensusErr) {
      if (tryRecoverStaleCache(expectedBuild)) {
        return;
      }
      errors.push(String(consensusErr.message || consensusErr));
    }
  }

  const assetVersions = readScriptAssetVersions();
  if (assetVersions.size > 1) {
    errors.push(`Mixed asset cache versions in index.html: ${Array.from(assetVersions).sort().join(", ")}.`);
  }

  const boot = {
    ready: errors.length === 0,
    errors,
    assetVersion: htmlVersion || (assetVersions.size === 1 ? Array.from(assetVersions)[0] : null),
    schemaVersion,
    async verifyBuildManifest() {
      try {
        const res = await fetch("/nr2-build.json", { cache: "no-store" });
        if (!res.ok) return { ok: true, skipped: true };
        const manifest = await res.json();
        const manifestVersion =
          (manifest && (manifest.BUILD_ID || manifest.schemaVersion || manifest.assetVersion)) || null;
        if (manifestVersion && schemaVersion && manifestVersion !== schemaVersion) {
          return {
            ok: false,
            mode: "manifest",
            manifestVersion,
            jsVersion: schemaVersion,
          };
        }
        return { ok: true, manifestVersion: manifestVersion || null };
      } catch {
        return { ok: true, skipped: true };
      }
    },
    async verifyDesktopManifest() {
      const manifestCheck = await boot.verifyBuildManifest();
      if (!manifestCheck.ok) return manifestCheck;
      const workstationOnly =
        !(
          typeof globalThis !== "undefined" && globalThis.NR2_FINANCIAL_ONLY
        ) &&
        (typeof WorkstationSchema !== "undefined" ||
          (typeof globalThis !== "undefined" && globalThis.NR2_WORKSTATION_ONLY));
      if (workstationOnly) {
        if (!window.pywebview || !window.pywebview.api) {
          return {
            ok: false,
            mode: "workstation-desktop-required",
            error: "NR2 Workstation must run in the desktop app — close any browser tab and launch Start Workstation.",
          };
        }
      }
      const hasPywebview = Boolean(
        window.DesktopBridge && DesktopBridge.hasDesktopApi && DesktopBridge.hasDesktopApi(),
      );
      const hasLoopback = Boolean(
        window.DesktopBridge && DesktopBridge.hasLoopbackApi && DesktopBridge.hasLoopbackApi(),
      );
      if (!hasPywebview) {
        if (workstationOnly) {
          return {
            ok: false,
            mode: "workstation-desktop-required",
            error: "NR2 Workstation must run in the desktop app — close any browser tab and launch Start Workstation.",
          };
        }
        if (hasLoopback) {
          try {
            const info = await DesktopBridge.getAppInfo();
            const serverVersion = info && (info.designSchemaVersion || info.assetVersion);
            if (serverVersion && schemaVersion && serverVersion !== schemaVersion) {
              return {
                ok: false,
                mode: "browser",
                serverVersion,
                pythonVersion: serverVersion,
                jsVersion: schemaVersion,
              };
            }
            return { ok: true, mode: "browser", serverVersion: serverVersion || null };
          } catch (err) {
            return { ok: false, mode: "browser", error: String(err && err.message ? err.message : err) };
          }
        }
        return { ok: true, mode: "offline" };
      }
      try {
        const info = await DesktopBridge.getAppInfo();
        const pyVersion = info && (info.designSchemaVersion || info.assetVersion);
        if (pyVersion && schemaVersion && pyVersion !== schemaVersion) {
          return {
            ok: false,
            mode: "desktop",
            pythonVersion: pyVersion,
            jsVersion: schemaVersion,
          };
        }
        return { ok: true, mode: "desktop", pythonVersion: pyVersion || null };
      } catch (err) {
        return { ok: false, mode: "desktop", error: String(err && err.message ? err.message : err) };
      }
    },
  };

  if (!boot.ready) {
    renderBootFailure("Design schema failed to load", errors);
  }

  if (typeof navigator !== "undefined" && navigator.serviceWorker && location.protocol.startsWith("http") && !isWorkstationApp()) {
    const mockEmbed =
      (typeof window !== "undefined" && window.NR2_STAFF_MOCK_ONLY) ||
      document.documentElement.getAttribute("data-nr2-staff-render") === "mock-embed";
    if (mockEmbed || window.__NR2_PURGE_ON_LOAD) {
      navigator.serviceWorker
        .getRegistrations()
        .then((regs) => Promise.all(regs.map((r) => r.unregister())))
        .catch(() => {});
    } else {
      const swTag = schemaVersion ? `sw.js?v=${schemaVersion}` : "sw.js";
      navigator.serviceWorker.register(swTag).catch(() => {});
    }
  }

  globalThis.NR2Boot = boot;
  globalThis.emergencyPurgeAndReload = emergencyPurgeAndReload;

  fetch("/nr2-build.json", { cache: "no-store" })
    .then((res) => (res.ok ? res.json() : null))
    .then((json) => {
      if (json) window.NR2_BUILD = json;
    })
    .catch(() => {});

  const urlBuild = new URL(location.href).searchParams.get("v");
  if (urlBuild && urlBuild !== REQUIRED_BUILD) {
    emergencyPurgeAndReload("URL build mismatch: " + urlBuild);
    return;
  }

  if (window.__nr2_boot_timer) clearTimeout(window.__nr2_boot_timer);
  window.__nr2_boot_timer = setTimeout(() => {
    verifyBuildConsensusManifest();
    if (!isWorkstationApp()) {
      setTimeout(assertMockupShell, 1200);
    }
  }, 0);
})();





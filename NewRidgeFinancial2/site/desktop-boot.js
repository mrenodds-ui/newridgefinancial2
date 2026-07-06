/**
 * Desktop boot gate — verify schema shell loaded and all assets share one build version.
 * Runs after page-schema.js + page-chrome.js, before app.js.
 */
(function () {
  const errors = [];

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

  function expectedSchemaVersion() {
    if (typeof WorkstationSchema !== "undefined" && WorkstationSchema.SCHEMA_VERSION) {
      return String(WorkstationSchema.SCHEMA_VERSION);
    }
    if (typeof PageSchema !== "undefined" && PageSchema.SCHEMA_VERSION) {
      return String(PageSchema.SCHEMA_VERSION);
    }
    return null;
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
      `<strong class="pv-state__title">${String(message).replace(/</g, "&lt;")}</strong>` +
      (detailHtml ? `<ul class="pv-state__list">${detailHtml}</ul>` : "") +
      `<p class="pv-state__msg">Close the window and launch <strong>${typeof WorkstationSchema !== "undefined" ? "Start Workstation" : "Start Program"}</strong> again. If this persists, run scripts/Refresh-NR2-DesktopShortcut.ps1.</p>`;
    if (typeof WorkstationSchema !== "undefined" && frame.querySelector("#workstationPage")) {
      let banner = frame.querySelector(".nr2-boot-error");
      if (!banner) {
        banner = document.createElement("div");
        banner.className = "pv-state pv-state--error nr2-boot-error ws-boot-error";
        banner.setAttribute("role", "alert");
        frame.insertBefore(banner, frame.firstChild);
      }
      banner.innerHTML = inner;
      return;
    }
    frame.innerHTML = `<div class="pv-state pv-state--error nr2-boot-error" role="alert">${inner}</div>`;
  }

  const schemaVersion = expectedSchemaVersion();
  if (!schemaVersion) {
    errors.push("page-schema.js did not define PageSchema.SCHEMA_VERSION.");
  }
  if (typeof PageChrome === "undefined") {
    errors.push("page-chrome.js failed to load (PageChrome is undefined).");
  }
  if (typeof PageSchema === "undefined" || typeof PageSchema.navPages !== "function") {
    if (typeof WorkstationSchema === "undefined") {
      errors.push("page-schema.js failed to load (PageSchema.navPages missing).");
    }
  }

  const assetVersions = readScriptAssetVersions();
  if (assetVersions.size > 1) {
    errors.push(`Mixed asset cache versions in index.html: ${Array.from(assetVersions).sort().join(", ")}.`);
  }
  if (schemaVersion && assetVersions.size === 1 && !assetVersions.has(schemaVersion)) {
    errors.push(
      `Schema version ${schemaVersion} does not match script cache bust ${Array.from(assetVersions)[0]}.`,
    );
  }

  const boot = {
    ready: errors.length === 0,
    errors,
    assetVersion: assetVersions.size === 1 ? Array.from(assetVersions)[0] : null,
    schemaVersion,
    async verifyBuildManifest() {
      try {
        const res = await fetch("/nr2-build.json", { cache: "no-store" });
        if (!res.ok) return { ok: true, skipped: true };
        const manifest = await res.json();
        const manifestVersion = manifest && (manifest.schemaVersion || manifest.assetVersion);
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
        typeof WorkstationSchema !== "undefined" ||
        (typeof globalThis !== "undefined" && globalThis.NR2_WORKSTATION_ONLY);
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

  if (typeof navigator !== "undefined" && navigator.serviceWorker && location.protocol.startsWith("http")) {
    navigator.serviceWorker.register("sw.js?v=hal-10025").catch(() => {});
  }

  globalThis.NR2Boot = boot;
})();

/**
 * Phase U3 — Dashboard layout apply (Moonshot REAUDIT3 NICE).
 * Reorders mosaic widgets from localStorage / server layout schema.
 * Preserves existing starship-bridge mosaic CSS — no theme rewrite.
 */
(function () {
  "use strict";

  const LS_PREFIX = "nr2:apex:layout:";

  function apiBase() {
    try {
      if (window.ApexCore && typeof window.ApexCore.apiBase === "function") {
        return window.ApexCore.apiBase();
      }
    } catch (_) {}
    return "/api/apex";
  }

  function loadLocal(page) {
    try {
      const raw = localStorage.getItem(LS_PREFIX + page);
      if (!raw) return null;
      const obj = JSON.parse(raw);
      return obj && typeof obj === "object" ? obj : null;
    } catch (_) {
      return null;
    }
  }

  function saveLocal(page, layout) {
    try {
      localStorage.setItem(LS_PREFIX + page, JSON.stringify(layout || {}));
    } catch (_) {}
  }

  function orderSpecs(specs, layout) {
    if (!Array.isArray(specs)) return specs;
    const grid = layout && Array.isArray(layout.grid) ? layout.grid : [];
    const orderMap = {};
    const spanMap = {};
    grid.forEach((c, i) => {
      if (!c || !c.id) return;
      orderMap[c.id] = typeof c.order === "number" ? c.order : i;
      spanMap[c.id] = c;
    });
    const ordered = specs.slice().sort((a, b) => {
      const aid = a && a.id;
      const bid = b && b.id;
      const ao = aid in orderMap ? orderMap[aid] : 1000;
      const bo = bid in orderMap ? orderMap[bid] : 1000;
      const ap = aid in orderMap ? 0 : 1;
      const bp = bid in orderMap ? 0 : 1;
      return ap - bp || ao - bo;
    });
    ordered.forEach((spec) => {
      if (!spec || !spec.id || !spanMap[spec.id]) return;
      const c = spanMap[spec.id];
      spec.layout = { x: c.x, y: c.y, w: c.w, h: c.h, order: c.order };
    });
    return ordered;
  }

  async function fetchLayout(page) {
    const p = String(page || "financial");
    try {
      const res = await fetch(`${apiBase()}/hal/dashboard-layout?page=${encodeURIComponent(p)}`, {
        credentials: "same-origin",
      });
      if (!res.ok) return loadLocal(p);
      const body = await res.json();
      if (body && body.ok && body.layout) {
        saveLocal(p, body.layout);
        return body.layout;
      }
    } catch (_) {}
    return loadLocal(p);
  }

  async function applyToSpecs(specs, page) {
    const layout = (await fetchLayout(page)) || loadLocal(page);
    if (!layout) return specs;
    return orderSpecs(specs, layout);
  }

  function markStage(root, page) {
    if (!root || !root.classList) return;
    root.classList.add("apex-stage-stack");
    root.dataset.layoutPhase = "U3";
    root.dataset.layoutPage = String(page || "");
  }

  window.Nr2DashboardLayout = {
    loadLocal,
    saveLocal,
    orderSpecs,
    fetchLayout,
    applyToSpecs,
    markStage,
    LS_PREFIX,
  };
})();

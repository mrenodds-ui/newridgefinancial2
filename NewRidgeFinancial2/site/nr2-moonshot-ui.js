/**
 * Moonshot Phase 8 UI — OCR inbox, audit dashboard, clinical bridge, close wizard, charts.
 */
const NR2MoonshotUI = (function () {
  function esc(v) {
    return String(v == null ? "" : v)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  async function fetchJson(path) {
    if (typeof DesktopBridge !== "undefined" && DesktopBridge.loopbackJson) {
      return DesktopBridge.loopbackJson(path);
    }
    const r = await fetch(path, { cache: "no-store" });
    return r.json();
  }

  async function postJson(path, body) {
    if (typeof DesktopBridge !== "undefined" && DesktopBridge.loopbackJson) {
      return DesktopBridge.loopbackJson(path, { method: "POST", body: JSON.stringify(body || {}) });
    }
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    return r.json();
  }

  async function resolveOcrItem(excId, action) {
    return postJson(`/api/ocr-exceptions/${encodeURIComponent(excId)}/resolve`, { action });
  }

  async function renderOcrExceptions(container) {
    if (!container) return;
    const data = await fetchJson("/api/ocr-exceptions?status=pending");
    const items = (data && data.items) || [];
    container.insertAdjacentHTML(
      "beforeend",
      `<section class="nr2-panel nr2-panel--ocr"><h3>OCR Exceptions (${items.length})</h3>` +
        (items.length
          ? `<ul class="nr2-ocr-list">${items
              .map(
                (it) =>
                  `<li data-ocr-id="${esc(it.id)}"><strong>${esc(it.sourceDoc || it.id)}</strong> · ${esc(it.confidenceLabel || "low")} · ${esc(
                    it.preview || "",
                  ).slice(0, 120)}` +
                  `<span class="nr2-ocr-actions">` +
                  `<button type="button" class="nr2-ocr-resolve" data-action="enqueue">Queue posting</button>` +
                  `<button type="button" class="nr2-ocr-resolve" data-action="discard">Discard</button>` +
                  `</span></li>`,
              )
              .join("")}</ul>`
          : `<p class="nr2-muted">No low-confidence OCR items pending.</p>`) +
        `</section>`,
    );
    container.querySelectorAll(".nr2-ocr-resolve").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const li = btn.closest("[data-ocr-id]");
        const id = li && li.getAttribute("data-ocr-id");
        if (!id) return;
        btn.disabled = true;
        try {
          await resolveOcrItem(id, btn.getAttribute("data-action") || "resolve");
          if (li) li.remove();
        } catch {
          btn.disabled = false;
        }
      });
    });
  }

  async function renderAuditDashboard(container) {
    if (!container) return;
    const data = await fetchJson("/api/audit-log/mutations?limit=40");
    const items = (data && data.items) || [];
    container.insertAdjacentHTML(
      "beforeend",
      `<section class="nr2-panel nr2-panel--audit"><h3>Audit Log</h3><ul class="nr2-audit-list">${items
        .slice(0, 15)
        .map((it) => `<li>${esc(it.ts || "")} · ${esc(it.action || "")} · ${esc(it.actor || "")}</li>`)
        .join("")}</ul></section>`,
    );
  }

  async function renderClinicalBridge(container) {
    if (!container) return;
    const data = await fetchJson("/api/clinical-summaries?limit=5");
    const items = (data && data.items) || [];
    container.insertAdjacentHTML(
      "beforeend",
      `<section class="nr2-panel nr2-panel--clinical"><h3>Clinical Context (8766)</h3>` +
        `<textarea class="nr2-clinical-paste" rows="3" placeholder="Paste SideNotes clinical narrative for HAL claims context…"></textarea>` +
        (items.length
          ? `<ul>${items.map((it) => `<li>${esc(it.summary || it.text || "")}</li>`).join("")}</ul>`
          : `<p class="nr2-muted">No recent SideNotes summaries.</p>`) +
        `</section>`,
    );
  }

  function renderCloseWizard(container) {
    if (!container) return;
    container.insertAdjacentHTML(
      "beforeend",
      `<section class="nr2-panel nr2-panel--wizard"><h3>Month-End Close Wizard</h3>` +
        `<ol class="nr2-wizard-steps"><li>Verify import freshness</li><li>Confirm backup</li><li>Run HAL reconciliation</li><li>Approve closeout</li></ol>` +
        `<button type="button" class="nr2-wizard-run" data-nr2-close-wizard>Start wizard</button></section>`,
    );
    const btn = container.querySelector("[data-nr2-close-wizard]");
    if (btn) {
      btn.addEventListener("click", async () => {
        const health = await fetchJson("/api/health");
        const readiness = await fetchJson("/api/import-readiness?operation=posting");
        alert(
          `Close wizard check:\nDB: ${health.db ? "OK" : "FAIL"}\nOllama: ${health.ollama ? "OK" : "FAIL"}\nImport: ${readiness.level}`,
        );
      });
    }
  }

  function mapKanbanColumns(postingItems, ocrItems) {
    const today = new Date().toISOString().slice(0, 10);
    const items = Array.isArray(postingItems) ? postingItems : [];
    const ocr = Array.isArray(ocrItems) ? ocrItems : [];
    return {
      pendingOcr: ocr.map((it) => ({
        id: it.id,
        description: it.sourceDoc || it.id,
        amount: it.confidenceLabel,
      })),
      ready: items
        .filter((it) => it.status === "pending_review")
        .map((it) => ({ id: it.queueId, description: it.description, amount: it.amount })),
      exceptions: items
        .filter((it) => it.status === "rejected")
        .map((it) => ({ id: it.queueId, description: it.description, amount: it.amount })),
      postedToday: items
        .filter((it) => it.status === "approved" && String(it.reviewedAtUtc || "").slice(0, 10) === today)
        .map((it) => ({ id: it.queueId, description: it.description, amount: it.amount })),
    };
  }

  async function renderCharts(pageId, container) {
    if (!container || typeof NR2Charts === "undefined") return;
    if (pageId === "financial" || pageId === "ar") {
      const heat = document.createElement("canvas");
      heat.id = "nr2-ar-heatmap";
      heat.width = 360;
      heat.height = 140;
      container.appendChild(heat);
      let buckets = [];
      try {
        const reports = await fetchJson("/api/financial-reports");
        buckets = (reports && reports.arAgingBuckets) || [];
      } catch {
        buckets = [];
      }
      if (!buckets.length) {
        buckets = [
          { bucket: "0-30", amount: 0 },
          { bucket: "31-60", amount: 0 },
          { bucket: "61-90", amount: 0 },
          { bucket: "90+", amount: 0 },
        ];
      }
      NR2Charts.renderARHeatmap("nr2-ar-heatmap", buckets);
    }
    if (pageId === "financial" || pageId === "quickbooks") {
      const timeline = document.createElement("canvas");
      timeline.id = "nr2-import-timeline";
      timeline.width = 360;
      timeline.height = 120;
      container.appendChild(timeline);
      let sources = null;
      try {
        const readiness = await fetchJson("/api/v1/import-readiness");
        sources = readiness && readiness.sources;
      } catch {
        sources = null;
      }
      if (!sources) {
        const cached =
          typeof DesktopBridge !== "undefined" && DesktopBridge.getCachedImportReadiness
            ? DesktopBridge.getCachedImportReadiness()
            : null;
        sources = (cached && cached.sources) || [
          { id: "bundle", name: "Import bundle", lastSyncAt: cached && cached.loadedAt, level: cached && cached.level },
        ];
      }
      NR2Charts.renderImportTimeline("nr2-import-timeline", sources);
    }
    if (pageId === "documents" || pageId === "financial") {
      const kanban = document.createElement("div");
      kanban.id = "nr2-posting-kanban";
      container.appendChild(kanban);
      let posting = { items: [] };
      let ocr = { items: [] };
      try {
        posting = await fetchJson("/api/posting-queue?limit=50");
        ocr = await fetchJson("/api/ocr-exceptions?status=pending");
      } catch {
        /* optional */
      }
      NR2Charts.renderPostingKanban("nr2-posting-kanban", mapKanbanColumns(posting.items, ocr.items));
    }
  }

  async function enhancePage(pageId, root) {
    if (!root) return;
    const panelHost = root.querySelector(".pv-canvas-body") || root.querySelector(".pv-body") || root;
    if (!panelHost || panelHost.dataset.nr2MoonshotEnhanced) return;
    panelHost.dataset.nr2MoonshotEnhanced = "1";
    await renderCharts(pageId, panelHost);
    if (pageId === "documents") await renderOcrExceptions(panelHost);
    if (pageId === "financial" || pageId === "settings") await renderAuditDashboard(panelHost);
    if (pageId === "claims" || pageId === "financial") await renderClinicalBridge(panelHost);
    if (pageId === "financial" || pageId === "taxes") renderCloseWizard(panelHost);
  }

  return { enhancePage };
})();

if (typeof window !== "undefined") window.NR2MoonshotUI = NR2MoonshotUI;

/**
 * Runtime bridge — SQLite-backed storage and practice data via loopback HTTP on port 8765.
 * Workstation (8766) still uses pywebview; the financial program is browser-only at 8765.
 */
const DesktopBridge = (function () {
  function isLoopbackHost() {
    if (typeof window === "undefined" || !window.location) return false;
    const protocol = String(window.location.protocol || "").toLowerCase();
    if (protocol !== "http:" && protocol !== "https:") return false;
    const host = String(window.location.hostname || "").toLowerCase();
    return host === "127.0.0.1" || host === "localhost" || host === "::1";
  }

  function hasDesktopApi() {
    if (typeof window === "undefined") return false;
    return Boolean(window.pywebview && window.pywebview.api);
  }

  function hasLoopbackApi() {
    if (!isLoopbackHost()) return false;
    if (typeof fetch !== "function") return false;
    if (typeof globalThis !== "undefined" && globalThis.NR2_WORKSTATION_ONLY) {
      return Boolean(hasDesktopApi());
    }
    return true;
  }

  function hasRuntimeAccess() {
    return hasDesktopApi() || hasLoopbackApi();
  }

  function loopbackUrl(path) {
    if (typeof window === "undefined" || !window.location) {
      return `https://127.0.0.1:8765${path}`;
    }
    if (typeof globalThis !== "undefined" && globalThis.NR2_WORKSTATION_ONLY) {
      const hub =
        (typeof window !== "undefined" && window.NR2_HAL_HUB_URL) ||
        (typeof window !== "undefined" && window.NR2_BUILD && window.NR2_BUILD.halHubUrl) ||
        "http://127.0.0.1:8765";
      return `${String(hub).replace(/\/+$/, "")}${path}`;
    }
    const port = window.location.port || "8765";
    const host = (typeof window !== "undefined" && window.location && window.location.hostname) || "127.0.0.1";
    const protocol = (typeof window !== "undefined" && window.location && window.location.protocol) || "http:";
    return `${protocol}//${host}:${port}${path}`;
  }

  let loopbackSessionToken = null;
  let loopbackSessionPromise = null;
  let importReadinessCache = null;
  let cloudHalSettingsCache = null;

  function readinessFingerprint(readiness) {
    if (!readiness || typeof readiness !== "object") return "";
    return [
      readiness.level || "",
      readiness.ok === true ? "1" : "0",
      readiness.loadedAt || "",
      readiness.error || "",
      Array.isArray(readiness.codes) ? readiness.codes.join(",") : "",
    ].join("|");
  }

  function notifyImportReadinessChanged(readiness) {
    if (readiness && typeof readiness === "object") {
      const nextFp = readinessFingerprint(readiness);
      const prevFp = readinessFingerprint(importReadinessCache);
      importReadinessCache = readiness;
      if (nextFp && nextFp === prevFp) return false;
    } else if (readiness == null && importReadinessCache == null) {
      return false;
    } else {
      importReadinessCache = readiness;
    }
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("nr2-import-readiness-changed", { detail: importReadinessCache }));
    }
    return true;
  }

  function notifyCloudHalChanged(settings) {
    if (settings && typeof settings === "object") cloudHalSettingsCache = settings;
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("nr2-cloud-hal-changed", { detail: cloudHalSettingsCache }));
    }
  }

  async function ensureLoopbackSession() {
    if (!hasLoopbackApi()) return null;
    if (loopbackSessionToken) return loopbackSessionToken;
    if (loopbackSessionPromise) return loopbackSessionPromise;
    loopbackSessionPromise = (async () => {
      try {
        const resp = await fetch(loopbackUrl("/api/app-info"), { cache: "no-store" });
        if (!resp.ok) return null;
        const refresh = resp.headers.get("X-NR2-Refresh-Token");
        if (refresh) loopbackSessionToken = refresh;
        const info = await resp.json();
        loopbackSessionToken = (info && (info.sessionToken || info.csrfToken)) || loopbackSessionToken;
        if (info && info.hubToken && typeof window !== "undefined") {
          window.NR2_HUB_TOKEN = String(info.hubToken);
        }
        importReadinessCache = (info && info.importReadiness) || importReadinessCache;
        cloudHalSettingsCache = (info && info.cloudHal) || cloudHalSettingsCache;
        if (info && info.importReadiness) notifyImportReadinessChanged(info.importReadiness);
        if (info && info.cloudHal) notifyCloudHalChanged(info.cloudHal);
        return loopbackSessionToken;
      } catch {
        return null;
      } finally {
        loopbackSessionPromise = null;
      }
    })();
    return loopbackSessionPromise;
  }

  async function loopbackJson(path, options, _retried) {
    const opts = Object.assign({ cache: "no-store" }, options || {});
    if (hasLoopbackApi()) {
      const token = await ensureLoopbackSession();
      opts.headers = Object.assign({}, opts.headers || {});
      if (token) opts.headers["X-NR2-Session-Token"] = token;
      const tabId = sessionStorage.getItem("nr2TabId");
      if (tabId) opts.headers["X-NR2-Tab-ID"] = tabId;
    }
    const method = String(opts.method || "GET").toUpperCase();
    const resp = await fetch(loopbackUrl(path), opts);
    const refresh = resp.headers.get("X-NR2-Refresh-Token");
    if (refresh) loopbackSessionToken = refresh;
    if (resp.status === 403 && !_retried && refresh && hasLoopbackApi()) {
      loopbackSessionToken = refresh;
      return loopbackJson(path, options, true);
    }
    if (!resp.ok) {
      let detail = "";
      try {
        const body = await resp.json();
        detail = (body && (body.error || body.detail)) || JSON.stringify(body);
      } catch {
        detail = await resp.text().catch(() => "");
      }
      const err = new Error(detail ? `HTTP ${resp.status}: ${detail}` : `HTTP ${resp.status} for ${path}`);
      err.status = resp.status;
      err.detail = detail;
      throw err;
    }
    return resp.json();
  }

  function runtimeMode() {
    if (hasLoopbackApi()) return "browser";
    if (hasDesktopApi()) return "desktop";
    return "offline";
  }

  function desktopRequiredMessage(feature) {
    const label = feature || "This feature";
    if (typeof globalThis !== "undefined" && globalThis.NR2_WORKSTATION_ONLY) {
      return `${label} requires the NR2 Workstation desktop app. Launch Start Workstation.`;
    }
    return `${label} requires the NR2 server. Run StartProgram.bat and open http://127.0.0.1:8765/ in your browser.`;
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

    if (hasLoopbackApi()) {
      ensureLoopbackSession().finally(finish);
      window.addEventListener("pywebviewready", finish, { once: true });
      window.setTimeout(finish, 2500);
      return;
    }

    window.addEventListener("pywebviewready", finish, { once: true });
    window.setTimeout(finish, 1500);
  }

  async function readDataFile(name) {
    if (hasDesktopApi()) {
      const text = await window.pywebview.api.read_data_file(name);
      return JSON.parse(text);
    }
    const response = await fetch(`/data/${name}`, { cache: "no-store" });
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
    if (hasLoopbackApi()) {
      try {
        const payload = await loopbackJson(`/api/storage/${encodeURIComponent(key)}`);
        return parseStorageValue(payload && payload.value);
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
    if (hasLoopbackApi()) {
      try {
        await loopbackJson(`/api/storage/${encodeURIComponent(key)}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: payload,
        });
        return;
      } catch {
        /* fall through to sessionStorage */
      }
    }
    try {
      sessionStorage.setItem(key, payload);
    } catch {
      /* storage may be unavailable */
    }
  }

  async function getImportReadiness() {
    if (hasLoopbackApi()) {
      try {
        importReadinessCache = await loopbackJson("/api/import-readiness");
        notifyImportReadinessChanged(importReadinessCache);
        return importReadinessCache;
      } catch {
        return importReadinessCache;
      }
    }
    return importReadinessCache;
  }

  async function evaluateHalQuery(payload) {
    if (!hasLoopbackApi()) throw new Error("HAL gateway requires loopback server");
    const body = Object.assign({}, payload || {});
    if (!body.shiftContext && typeof window !== "undefined" && window.nr2ShiftState) {
      body.shiftContext = window.nr2ShiftState;
    }
    if (body.stream && typeof body.onToken === "function") {
      return evaluateHalQueryStream(body, body.onToken, body.signal);
    }
    return loopbackJson("/api/hal/evaluate-query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  async function evaluateHalQueryStream(payload, onToken, abortSignal) {
    if (!hasLoopbackApi()) throw new Error("HAL gateway requires loopback server");
    const body = Object.assign({}, payload || {});
    delete body.onToken;
    delete body.signal;
    if (!body.shiftContext && typeof window !== "undefined" && window.nr2ShiftState) {
      body.shiftContext = window.nr2ShiftState;
    }
    const token = await ensureLoopbackSession();
    const headers = { "Content-Type": "application/json" };
    if (token) headers["X-NR2-Session-Token"] = token;
    const resp = await fetch(loopbackUrl("/api/v1/hal/stream-sse"), {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      cache: "no-store",
      signal: abortSignal,
    });
    if (!resp.ok) {
      const detail = await resp.text().catch(() => "");
      throw new Error(`HTTP ${resp.status}: ${detail}`);
    }
    const lane = resp.headers.get("X-HAL-Lane-Used") || "";
    let full = "";
    let resolvedLane = lane;
    const reader = resp.body && resp.body.getReader ? resp.body.getReader() : null;
    if (!reader) {
      return { ok: false, error: "stream_unsupported" };
    }
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";
      for (const part of parts) {
        const lines = part.split("\n");
        let eventType = "message";
        let dataLine = "";
        for (const line of lines) {
          if (line.startsWith("event:")) eventType = line.slice(6).trim();
          if (line.startsWith("data:")) dataLine = line.slice(5).trim();
        }
        if (!dataLine) continue;
        let obj;
        try {
          obj = JSON.parse(dataLine);
        } catch {
          continue;
        }
        if (eventType === "meta" && obj.lane) {
          resolvedLane = obj.lane;
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("nr2-hal-lane-used", { detail: { lane: obj.lane, routingReason: obj.routingReason } }));
          }
          continue;
        }
        if (eventType === "error" && obj.error) {
          throw new Error(obj.error);
        }
        if (obj.token) {
          full += obj.token;
          if (typeof onToken === "function") onToken(obj.token);
        }
        if (obj.done) break;
      }
    }
    return {
      ok: true,
      text: full,
      message: { content: full },
      resolvedLane,
      streamed: true,
    };
  }

  let shiftPollTimer = null;

  async function pollShiftState() {
    if (!hasLoopbackApi()) return null;
    try {
      const state = await loopbackJson("/api/employee/current-shift");
      if (typeof window !== "undefined") {
        window.nr2ShiftState = state;
        window.dispatchEvent(new CustomEvent("nr2-shift-state-changed", { detail: state }));
      }
      return state;
    } catch {
      return typeof window !== "undefined" ? window.nr2ShiftState : null;
    }
  }

  function startShiftPolling(intervalMs) {
    const ms = Number(intervalMs || 60000);
    if (shiftPollTimer) return;
    pollShiftState().catch(() => {});
    shiftPollTimer = setInterval(() => {
      pollShiftState().catch(() => {});
    }, ms);
  }

  async function fetchClinicalContext(options) {
    if (!hasLoopbackApi()) return { ok: false, items: [] };
    const opts = options && typeof options === "object" ? options : {};
    const limit = opts.limit != null ? Number(opts.limit) : 5;
    const patientId = opts.patientId ? String(opts.patientId) : "";
    const q = patientId
      ? `?limit=${encodeURIComponent(String(limit))}&patientId=${encodeURIComponent(patientId)}`
      : `?limit=${encodeURIComponent(String(limit))}`;
    return loopbackJson(`/api/clinical-summaries${q}`);
  }

  async function fetchStandingConsent(actionType, amount) {
    if (!hasLoopbackApi()) return { ok: false, allowed: false };
    const q = amount != null ? `?amount=${encodeURIComponent(String(amount))}` : "";
    return loopbackJson(`/api/employee/standing-consent/${encodeURIComponent(String(actionType || ""))}${q}`);
  }

  async function explainHalBlock(payload) {
    if (!hasLoopbackApi()) return { ok: false };
    return loopbackJson("/api/audit/explain-block", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });
  }

  async function fetchHalSessionAudit(sessionId) {
    if (!hasLoopbackApi()) return { ok: false };
    return loopbackJson(`/api/audit/hal-session/${encodeURIComponent(String(sessionId || ""))}`);
  }

  async function fetchHalImportGuard(query) {
    if (!hasLoopbackApi()) return { blocked: false };
    const q = encodeURIComponent(String(query || ""));
    return loopbackJson(`/api/hal/import-guard?q=${q}`);
  }

  async function getCloudHalSettings() {
    if (cloudHalSettingsCache) return cloudHalSettingsCache;
    if (hasLoopbackApi()) {
      try {
        cloudHalSettingsCache = await loopbackJson("/api/settings/cloud-hal");
        return cloudHalSettingsCache;
      } catch {
        return { enabled: false };
      }
    }
    return { enabled: false };
  }

  async function setCloudHalEnabled(enable, enabledBy) {
    if (!hasLoopbackApi()) throw new Error("Cloud HAL settings require loopback server");
    const payload = enable
      ? { enable: true, confirm: "ENABLE CLOUD HAL", enabledBy: enabledBy || "Staff" }
      : { enable: false, enabledBy: enabledBy || "Staff" };
    const result = await loopbackJson("/api/settings/cloud-hal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    cloudHalSettingsCache = (result && result.settings) || cloudHalSettingsCache;
    notifyCloudHalChanged(cloudHalSettingsCache);
    return result;
  }

  async function getAppInfo() {
    if (hasDesktopApi()) return window.pywebview.api.get_app_info();
    if (hasLoopbackApi()) {
      try {
        return await loopbackJson("/api/app-info");
      } catch {
        return { mode: "loopback", version: "2.0" };
      }
    }
    return { mode: "file", version: "2.0" };
  }

  async function getImportBundle() {
    if (hasDesktopApi() && window.pywebview.api.get_import_bundle) {
      return window.pywebview.api.get_import_bundle();
    }
    if (hasLoopbackApi()) {
      try {
        return await loopbackJson("/api/import-bundle");
      } catch {
        return null;
      }
    }
    return null;
  }

  async function getImportSyncStatus() {
    if (hasDesktopApi() && window.pywebview.api.get_import_sync_status) {
      return window.pywebview.api.get_import_sync_status();
    }
    if (hasLoopbackApi()) {
      try {
        return await loopbackJson("/api/import-sync-status");
      } catch {
        return { status: "idle" };
      }
    }
    return { status: "idle" };
  }

  async function refreshImports() {
    if (hasDesktopApi() && window.pywebview.api.refresh_imports) {
      return window.pywebview.api.refresh_imports();
    }
    if (hasLoopbackApi()) {
      try {
        return await loopbackJson("/api/refresh-imports", { method: "POST" });
      } catch {
        return getImportBundle();
      }
    }
    return getImportBundle();
  }

  async function syncAccountingDocuments() {
    if (hasDesktopApi() && window.pywebview.api.sync_accounting_documents) {
      return window.pywebview.api.sync_accounting_documents();
    }
    if (hasLoopbackApi()) {
      try {
        return await loopbackJson("/api/sync-documents");
      } catch {
        return null;
      }
    }
    return null;
  }

  async function listPracticeSourceCatalog() {
    if (hasDesktopApi() && window.pywebview.api.list_practice_source_catalog) {
      return window.pywebview.api.list_practice_source_catalog();
    }
    if (hasLoopbackApi()) {
      try {
        return await loopbackJson("/api/practice-source-catalog");
      } catch {
        return null;
      }
    }
    return null;
  }

  async function fetchPracticeSource(system, resource, options) {
    if (hasDesktopApi() && window.pywebview.api.fetch_practice_source) {
      const payload = options && typeof options === "object" ? JSON.stringify(options) : "{}";
      return window.pywebview.api.fetch_practice_source(system, resource, payload);
    }
    if (hasLoopbackApi()) {
      try {
        return await loopbackJson("/api/fetch-practice-source", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            system: String(system || ""),
            resource: String(resource || ""),
            options: options && typeof options === "object" ? options : {},
          }),
        });
      } catch {
        return null;
      }
    }
    return null;
  }

  async function pullPracticeSources(options) {
    const opts = options && typeof options === "object" ? options : {};
    if (hasDesktopApi() && window.pywebview.api.pull_practice_sources) {
      return window.pywebview.api.pull_practice_sources(JSON.stringify(opts));
    }
    if (hasLoopbackApi()) {
      try {
        return await loopbackJson("/api/pull-practice-sources", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(opts),
        });
      } catch {
        return null;
      }
    }
    return null;
  }

  async function getChartOfAccounts() {
    if (hasDesktopApi() && window.pywebview.api.get_chart_of_accounts) {
      return window.pywebview.api.get_chart_of_accounts();
    }
    return null;
  }

  async function draftJournalEntry({ description, period, amount, context }) {
    if (hasDesktopApi() && window.pywebview.api.draft_journal_entry) {
      return window.pywebview.api.draft_journal_entry(
        String(description || ""),
        String(period || ""),
        Number(amount || 0),
        JSON.stringify(context || {}),
      );
    }
    return null;
  }

  async function listPostingQueue(options) {
    if (hasDesktopApi() && window.pywebview.api.list_posting_queue) {
      const limit = options && options.limit != null ? Number(options.limit) : 20;
      const status = options && options.status ? String(options.status) : "";
      return window.pywebview.api.list_posting_queue(limit, status);
    }
    if (hasLoopbackApi()) {
      try {
        return await loopbackJson("/api/financial/post-queue");
      } catch (err) {
        try {
          return await loopbackJson("/api/posting-queue");
        } catch (err2) {
          const status = Number((err2 && err2.status) || (err && err.status) || 0);
          // Import-readiness 403 means the server is up but temporarily gated —
          // treat as an available empty queue so live-wire does not say "unavailable".
          if (status === 403 || status === 409) {
            return {
              items: [],
              metrics: { pendingReview: 0, approved: 0, rejected: 0, total: 0 },
              unavailable: false,
              gated: true,
              gateStatus: status,
            };
          }
          return { items: [], metrics: { pendingReview: 0, approved: 0, rejected: 0, total: 0 }, unavailable: true };
        }
      }
    }
    return { items: [], metrics: { pendingReview: 0, approved: 0, rejected: 0, total: 0 }, unavailable: true };
  }

  async function enqueueJournalPosting(payload) {
    if (hasDesktopApi() && window.pywebview.api.enqueue_journal_posting) {
      return window.pywebview.api.enqueue_journal_posting(JSON.stringify(payload || {}));
    }
    if (hasLoopbackApi()) {
      return loopbackJson("/api/posting-queue/enqueue", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
      });
    }
    throw new Error(desktopRequiredMessage("Journal posting queue"));
  }

  async function reviewPostingQueueEntry(queueId, action, reviewerActor, reviewNote) {
    if (hasDesktopApi() && window.pywebview.api.review_posting_queue_entry) {
      return window.pywebview.api.review_posting_queue_entry(
        String(queueId || ""),
        String(action || ""),
        String(reviewerActor || ""),
        String(reviewNote || ""),
      );
    }
    if (hasLoopbackApi()) {
      return loopbackJson("/api/posting-queue/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          queueId: String(queueId || ""),
          action: String(action || ""),
          reviewerActor: String(reviewerActor || ""),
          reviewNote: String(reviewNote || ""),
        }),
      });
    }
    throw new Error(desktopRequiredMessage("Posting queue review"));
  }

  async function bulkReviewPostingQueue(action, reviewerActor, reviewNote) {
    if (hasDesktopApi() && window.pywebview.api.bulk_review_posting_queue) {
      return window.pywebview.api.bulk_review_posting_queue(
        String(action || "approved"),
        String(reviewerActor || "local-user"),
        String(reviewNote || ""),
      );
    }
    if (hasLoopbackApi()) {
      return loopbackJson("/api/posting-queue/bulk-review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: String(action || "approved"),
          reviewerActor: String(reviewerActor || "local-user"),
          reviewNote: String(reviewNote || ""),
        }),
      });
    }
    throw new Error(desktopRequiredMessage("Bulk posting queue review"));
  }

  async function exportApprovedPostingQueue(options) {
    if (hasDesktopApi() && window.pywebview.api.export_approved_posting_queue) {
      const limit = options && options.limit != null ? Number(options.limit) : 200;
      return window.pywebview.api.export_approved_posting_queue(limit);
    }
    if (hasLoopbackApi()) {
      const limit = options && options.limit != null ? Number(options.limit) : 200;
      return loopbackJson("/api/posting-queue/export-approved", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ limit }),
      });
    }
    throw new Error(desktopRequiredMessage("Approved posting queue export"));
  }

  async function outboundPost(path, payload) {
    if (hasDesktopApi() && window.pywebview && window.pywebview.api) {
      const api = window.pywebview.api;
      if (path === "/api/outbound/email" && api.send_email_with_consent) {
        return api.send_email_with_consent(JSON.stringify(payload || {}));
      }
      if (path === "/api/outbound/qb-export" && api.export_posting_queue_iif_with_consent) {
        return api.export_posting_queue_iif_with_consent(JSON.stringify(payload || {}));
      }
      if (path === "/api/outbound/claim-packet" && api.build_claim_packet_with_consent) {
        return api.build_claim_packet_with_consent(JSON.stringify(payload || {}));
      }
      if (path === "/api/outbound/narrative-prep" && api.export_narrative_portal_prep_with_consent) {
        return api.export_narrative_portal_prep_with_consent(JSON.stringify(payload || {}));
      }
      if (path === "/api/outbound/qbo-post" && api.post_qbo_journal_with_consent) {
        return api.post_qbo_journal_with_consent(JSON.stringify(payload || {}));
      }
      if (path === "/api/outbound/payer-portal-rpa" && api.build_payer_portal_rpa_with_consent) {
        return api.build_payer_portal_rpa_with_consent(JSON.stringify(payload || {}));
      }
      if (path === "/api/outbound/softdent-writeback" && api.queue_softdent_writeback_with_consent) {
        return api.queue_softdent_writeback_with_consent(JSON.stringify(payload || {}));
      }
      if (path === "/api/outbound/briefing-email") {
        return outboundPost("/api/outbound/email", payload);
      }
    }
    if (hasLoopbackApi()) {
      return loopbackJson(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
      });
    }
    throw new Error(desktopRequiredMessage("Outbound actions"));
  }

  async function sendEmailWithConsent(payload) {
    return outboundPost("/api/outbound/email", payload || {});
  }

  async function exportPostingQueueIifWithConsent(payload) {
    return outboundPost("/api/outbound/qb-export", payload || {});
  }

  async function buildClaimPacketWithConsent(payload) {
    return outboundPost("/api/outbound/claim-packet", payload || {});
  }

  async function exportNarrativePortalPrepWithConsent(payload) {
    return outboundPost("/api/outbound/narrative-prep", payload || {});
  }

  async function postQboJournalWithConsent(payload) {
    return outboundPost("/api/outbound/qbo-post", payload || {});
  }

  async function buildPayerPortalRpaWithConsent(payload) {
    return outboundPost("/api/outbound/payer-portal-rpa", payload || {});
  }

  async function queueSoftdentWritebackWithConsent(payload) {
    return outboundPost("/api/outbound/softdent-writeback", payload || {});
  }

  async function softdentWritebackStatus() {
    if (hasDesktopApi() && window.pywebview.api.softdent_writeback_status) {
      return window.pywebview.api.softdent_writeback_status();
    }
    if (hasLoopbackApi()) {
      return loopbackJson("/api/outbound/softdent-writeback-status");
    }
    return { ok: false, configured: false, queued: 0 };
  }

  async function quickbooksOnlineStatus() {
    if (hasDesktopApi() && window.pywebview.api.quickbooks_online_status) {
      return window.pywebview.api.quickbooks_online_status();
    }
    if (hasLoopbackApi()) {
      return loopbackJson("/api/outbound/qbo-status");
    }
    return { ok: false, message: "QuickBooks Online status requires desktop or loopback runtime." };
  }

  async function listOutboundAudit(limit) {
    if (hasDesktopApi() && window.pywebview.api.list_outbound_audit) {
      return window.pywebview.api.list_outbound_audit(Number(limit || 15));
    }
    if (hasLoopbackApi()) {
      return loopbackJson(`/api/outbound/audit?limit=${encodeURIComponent(String(limit || 15))}`);
    }
    return { ok: true, items: [], count: 0 };
  }

  async function employeeStatus(targetLevel) {
    if (hasDesktopApi() && window.pywebview.api.employee_status) {
      return window.pywebview.api.employee_status(Number(targetLevel || 7));
    }
    if (hasLoopbackApi()) {
      return loopbackJson(`/api/employee/status?targetLevel=${encodeURIComponent(String(targetLevel || 7))}`);
    }
    return { ok: false, message: "Employee status requires desktop or loopback runtime." };
  }

  async function listEmployeeWorkLog(limit) {
    if (hasDesktopApi() && window.pywebview.api.list_employee_work_log) {
      return window.pywebview.api.list_employee_work_log(Number(limit || 20));
    }
    if (hasLoopbackApi()) {
      return loopbackJson(`/api/employee/work-log?limit=${encodeURIComponent(String(limit || 20))}`);
    }
    return { ok: true, items: [], count: 0 };
  }

  async function appendEmployeeWorkLog(payload) {
    if (hasDesktopApi() && window.pywebview.api.append_employee_work_log) {
      return window.pywebview.api.append_employee_work_log(JSON.stringify(payload || {}));
    }
    if (hasLoopbackApi()) {
      const host = window.location.hostname || "127.0.0.1";
      const port = window.location.port || "8765";
      const resp = await fetch(`${window.location.protocol}//${host}:${port}/api/employee/work-log`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
        cache: "no-store",
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return resp.json();
    }
    return { ok: false };
  }

  async function runEmployeeShift(payload) {
    if (hasDesktopApi() && window.pywebview.api.run_employee_shift) {
      return window.pywebview.api.run_employee_shift(JSON.stringify(payload || {}));
    }
    if (hasLoopbackApi()) {
      const host = window.location.hostname || "127.0.0.1";
      const port = window.location.port || "8765";
      const resp = await fetch(`${window.location.protocol}//${host}:${port}/api/employee/shift`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
        cache: "no-store",
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return resp.json();
    }
    return { ok: false, message: "Employee shift requires desktop or loopback runtime." };
  }

  async function webResearch(query, options) {
    const opts = options && typeof options === "object" ? options : {};
    if (hasDesktopApi() && window.pywebview.api.web_research) {
      return window.pywebview.api.web_research(String(query || ""), JSON.stringify(opts));
    }
    return {
      ok: false,
      error: "desktop_required",
      results: [],
      policy: "public_docs_only_no_phi",
    };
  }

  async function listHalMemories() {
    if (hasDesktopApi() && window.pywebview.api.list_hal_memories) {
      return window.pywebview.api.list_hal_memories();
    }
    if (hasLoopbackApi()) {
      try {
        return await loopbackJson("/api/hal-memories");
      } catch {
        return { items: [], count: 0 };
      }
    }
    return { items: [], count: 0 };
  }

  async function updateHalSessionContext(payload) {
    const body = payload && typeof payload === "object" ? payload : {};
    if (hasDesktopApi() && window.pywebview.api.update_hal_session_context) {
      return window.pywebview.api.update_hal_session_context(
        String(body.claimId || body.claim_id || ""),
        String(body.narrativeId || body.narrative_id || ""),
        String(body.page || ""),
        String(body.topic || ""),
        String(body.payer || ""),
      );
    }
    if (hasLoopbackApi()) {
      return loopbackJson("/api/hal-learning/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    }
    return { ok: false };
  }

  async function halLearningStatus() {
    if (hasDesktopApi() && window.pywebview.api.hal_learning_status) {
      return window.pywebview.api.hal_learning_status();
    }
    if (hasLoopbackApi()) {
      return loopbackJson("/api/hal-learning/status");
    }
    return { ok: false };
  }

  async function rememberHalFact(text, options) {
    const opts = options && typeof options === "object" ? options : {};
    if (hasDesktopApi() && window.pywebview.api.remember_hal_fact) {
      return window.pywebview.api.remember_hal_fact(
        String(text || ""),
        String(opts.source || "staff:remember"),
        String(opts.category || ""),
      );
    }
    if (hasLoopbackApi()) {
      return loopbackJson("/api/hal-memories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: String(text || ""),
          source: String(opts.source || "staff:remember"),
          category: String(opts.category || ""),
        }),
      });
    }
    throw new Error(desktopRequiredMessage("Saving HAL learned facts"));
  }

  async function rememberHalWebFindings(query, findings) {
    if (hasDesktopApi() && window.pywebview.api.remember_hal_web_findings) {
      return window.pywebview.api.remember_hal_web_findings(String(query || ""), JSON.stringify(findings || []));
    }
    throw new Error(desktopRequiredMessage("Saving HAL web findings"));
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

  async function getTaxPlan() {
    if (hasDesktopApi() && window.pywebview.api.get_tax_plan) {
      return window.pywebview.api.get_tax_plan();
    }
    if (typeof TaxEngine !== "undefined" && TaxEngine.buildTaxPlanFromSnapshot) {
      const snap =
        typeof SnapshotStore !== "undefined" && SnapshotStore.getCached
          ? SnapshotStore.getCached()
          : typeof globalThis !== "undefined"
            ? globalThis.__nr2ProgramSnapshot
            : null;
      const feed = typeof globalThis !== "undefined" ? globalThis.__nr2HalWidgetFeed : null;
      return TaxEngine.buildTaxPlanFromSnapshot(snap, feed);
    }
    return null;
  }

  async function getIntegrationHealth() {
    if (hasDesktopApi() && window.pywebview.api.get_integration_health) {
      return window.pywebview.api.get_integration_health();
    }
    if (hasLoopbackApi()) return loopbackJson("/api/integration-health");
    throw new Error(desktopRequiredMessage("Integration health"));
  }

  async function getAutomationRegistry() {
    if (hasDesktopApi() && window.pywebview.api.get_automation_registry) {
      return window.pywebview.api.get_automation_registry();
    }
    if (hasLoopbackApi()) return loopbackJson("/api/automation-registry");
    throw new Error(desktopRequiredMessage("Automation registry"));
  }

  async function buildSupportBundle(note) {
    if (hasDesktopApi() && window.pywebview.api.build_support_bundle) {
      return window.pywebview.api.build_support_bundle(String(note || ""));
    }
    if (hasLoopbackApi()) {
      return loopbackJson("/api/support-bundle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: String(note || "") }),
      });
    }
    throw new Error(desktopRequiredMessage("Support bundle"));
  }

  async function getFinancialReports(syncExports) {
    if (hasDesktopApi() && window.pywebview.api.get_financial_reports) {
      return window.pywebview.api.get_financial_reports(Boolean(syncExports));
    }
    if (hasLoopbackApi()) {
      const q = syncExports ? "?syncExports=1" : "";
      return loopbackJson(`/api/financial-reports${q}`);
    }
    throw new Error(desktopRequiredMessage("Financial reports"));
  }

  async function getDailyCloseout() {
    if (hasDesktopApi() && window.pywebview.api.get_daily_closeout) {
      return window.pywebview.api.get_daily_closeout();
    }
    if (hasLoopbackApi()) return loopbackJson("/api/daily-closeout");
    throw new Error(desktopRequiredMessage("Daily closeout"));
  }

  async function runProgramSelfHeal(options) {
    const opts = options || {};
    if (hasDesktopApi() && window.pywebview.api.run_program_self_heal) {
      return window.pywebview.api.run_program_self_heal(
        Boolean(opts.fullPull),
        Boolean(opts.documentsOnly),
        String(opts.reason || "ui"),
      );
    }
    if (hasLoopbackApi()) {
      return loopbackJson("/api/self-heal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fullPull: Boolean(opts.fullPull),
          documentsOnly: Boolean(opts.documentsOnly),
          reason: opts.reason || "ui",
        }),
      });
    }
    throw new Error(desktopRequiredMessage("Program self-heal"));
  }

  async function getProgramHelp(query) {
    if (hasDesktopApi() && window.pywebview.api.get_program_help) {
      return window.pywebview.api.get_program_help(String(query || ""));
    }
    return { text: "Program help requires the NR2 server.", match: null };
  }

  async function searchHalMemories(query, limit) {
    if (hasDesktopApi() && window.pywebview.api.search_hal_memories) {
      return window.pywebview.api.search_hal_memories(String(query || ""), Number(limit || 5));
    }
    return { items: [], count: 0, text: "" };
  }

  async function searchPayerReference(query, limit) {
    if (hasDesktopApi() && window.pywebview.api.search_payer_reference) {
      return window.pywebview.api.search_payer_reference(String(query || ""), Number(limit || 5));
    }
    if (hasLoopbackApi()) {
      try {
        const q = encodeURIComponent(String(query || ""));
        const lim = Number(limit || 5);
        return await loopbackJson(`/api/payer-reference?q=${q}&limit=${lim}`);
      } catch {
        return { items: [], count: 0, text: "" };
      }
    }
    return { items: [], count: 0, text: "" };
  }

  async function lookupFeeSchedule(query, limit) {
    if (hasDesktopApi() && window.pywebview.api.lookup_fee_schedule) {
      return window.pywebview.api.lookup_fee_schedule(String(query || ""), Number(limit || 3));
    }
    if (hasLoopbackApi()) {
      try {
        const q = encodeURIComponent(String(query || ""));
        const lim = Number(limit || 3);
        return await loopbackJson(`/api/fee-schedule?q=${q}&limit=${lim}`);
      } catch {
        return { items: [], count: 0, text: "" };
      }
    }
    return { items: [], count: 0, text: "" };
  }

  async function listEligibilityCache(limit) {
    if (hasDesktopApi() && window.pywebview.api.list_eligibility_cache) {
      return window.pywebview.api.list_eligibility_cache(Number(limit || 20));
    }
    if (hasLoopbackApi()) {
      try {
        return await loopbackJson(`/api/eligibility-cache?limit=${Number(limit || 20)}`);
      } catch {
        return { items: [], count: 0, text: "", summary: null };
      }
    }
    return { items: [], count: 0, text: "", summary: null };
  }

  async function upsertEligibilityCache(entry) {
    const payload = entry && typeof entry === "object" ? entry : {};
    if (hasDesktopApi() && window.pywebview.api.upsert_eligibility_cache) {
      return window.pywebview.api.upsert_eligibility_cache(JSON.stringify(payload));
    }
    if (hasLoopbackApi()) {
      return loopbackJson("/api/eligibility-cache", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entry: payload }),
      });
    }
    throw new Error(desktopRequiredMessage("Saving eligibility cache entries"));
  }

  async function searchEligibilityCache(query, limit) {
    if (hasDesktopApi() && window.pywebview.api.search_eligibility_cache) {
      return window.pywebview.api.search_eligibility_cache(String(query || ""), Number(limit || 10));
    }
    if (hasLoopbackApi()) {
      try {
        const q = encodeURIComponent(String(query || ""));
        const lim = Number(limit || 10);
        return await loopbackJson(`/api/eligibility-cache?q=${q}&limit=${lim}`);
      } catch {
        return { items: [], count: 0, text: "" };
      }
    }
    return { items: [], count: 0, text: "" };
  }

  async function fetchEligibility271(request) {
    const payload = request && typeof request === "object" ? request : {};
    if (hasDesktopApi() && window.pywebview.api.fetch_eligibility_271) {
      return window.pywebview.api.fetch_eligibility_271(JSON.stringify(payload));
    }
    if (hasLoopbackApi()) {
      return loopbackJson("/api/eligibility-cache/fetch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request: payload }),
      });
    }
    throw new Error(desktopRequiredMessage("Clearinghouse 271 fetch"));
  }

  async function clearinghouseStatus() {
    if (hasDesktopApi() && window.pywebview.api.clearinghouse_status) {
      return window.pywebview.api.clearinghouse_status();
    }
    if (hasLoopbackApi()) {
      try {
        return await loopbackJson("/api/eligibility-cache/status");
      } catch {
        return { ok: false, mockEnabled: false, liveReady: false };
      }
    }
    return { ok: false, mockEnabled: false, liveReady: false };
  }

  async function grepProgramSource(query, limit) {
    if (hasDesktopApi() && window.pywebview.api.grep_program_source) {
      return window.pywebview.api.grep_program_source(String(query || ""), Number(limit || 24));
    }
    return { hits: [], count: 0, text: "Program source search requires the NR2 server." };
  }

  async function readProgramFile(relPath, maxChars) {
    if (hasDesktopApi() && window.pywebview.api.read_program_file) {
      return window.pywebview.api.read_program_file(String(relPath || ""), Number(maxChars || 12000));
    }
    return { ok: false, text: "Program file read requires the NR2 server." };
  }

  async function listProgramFiles(subdir, limit) {
    if (hasDesktopApi() && window.pywebview.api.list_program_files) {
      return window.pywebview.api.list_program_files(String(subdir || "site"), Number(limit || 80));
    }
    return { ok: false, files: [], text: "Program file list requires the NR2 server." };
  }

  async function applyProgramPatch(relPath, oldString, newString, dryRun) {
    if (hasDesktopApi() && window.pywebview.api.apply_program_patch) {
      return window.pywebview.api.apply_program_patch(
        String(relPath || ""),
        String(oldString || ""),
        String(newString || ""),
        Boolean(dryRun),
      );
    }
    return { ok: false, text: "Program patch requires the NR2 server." };
  }

  async function runHalValidation(timeoutSec) {
    if (hasDesktopApi() && window.pywebview.api.run_hal_validation) {
      return window.pywebview.api.run_hal_validation(Number(timeoutSec || 120));
    }
    return { ok: false, text: "HAL validation requires the NR2 server.", exitCode: -1 };
  }

  async function runNodeSyntaxCheck(relPaths) {
    if (hasDesktopApi() && window.pywebview.api.run_node_syntax_check) {
      return window.pywebview.api.run_node_syntax_check(Array.isArray(relPaths) ? relPaths : []);
    }
    return { ok: false, text: "Syntax check requires the NR2 server.", results: [] };
  }

  async function semanticSearchProgram(query, limit) {
    if (hasDesktopApi() && window.pywebview.api.semantic_search_program) {
      return window.pywebview.api.semantic_search_program(String(query || ""), Number(limit || 15));
    }
    return { hits: [], count: 0, text: "Semantic search requires the NR2 server." };
  }

  async function runGitReadonly(command) {
    if (hasDesktopApi() && window.pywebview.api.run_git_readonly) {
      return window.pywebview.api.run_git_readonly(String(command || "status"));
    }
    return { ok: false, text: "Git read requires the NR2 server." };
  }

  async function runAllowlistedCommand(commandId) {
    if (hasDesktopApi() && window.pywebview.api.run_allowlisted_command) {
      return window.pywebview.api.run_allowlisted_command(String(commandId || "validate-hal"));
    }
    return { ok: false, text: "Allowlisted commands require the NR2 server." };
  }

  async function applyProgramPatches(patches, dryRun) {
    if (hasDesktopApi() && window.pywebview.api.apply_program_patches) {
      return window.pywebview.api.apply_program_patches(Array.isArray(patches) ? patches : [], Boolean(dryRun));
    }
    return { ok: false, text: "Batch patch requires the NR2 server.", count: 0 };
  }

  async function showWorkstationMessagePopup(payload) {
    if (hasDesktopApi() && window.pywebview.api.show_workstation_message_popup) {
      return window.pywebview.api.show_workstation_message_popup(payload || {});
    }
    return { ok: false, text: "Message popups require the NR2 Workstation app." };
  }

  async function flushMessagePopups() {
    if (hasDesktopApi() && window.pywebview.api.flush_message_popups) {
      return window.pywebview.api.flush_message_popups();
    }
    return { ok: false, count: 0 };
  }

  async function setPopupStation(name) {
    if (hasDesktopApi() && window.pywebview.api.set_popup_station) {
      return window.pywebview.api.set_popup_station(String(name || ""));
    }
    return { ok: false };
  }

  async function showWorkstationMainWindow() {
    if (hasDesktopApi() && window.pywebview.api.show_workstation_main_window) {
      return window.pywebview.api.show_workstation_main_window();
    }
    return { ok: false };
  }

  return {
    hasDesktopApi,
    hasLoopbackApi,
    hasRuntimeAccess,
    isLoopbackHost,
    runtimeMode,
    desktopRequiredMessage,
    whenReady,
    readDataFile,
    storageGet,
    storageSet,
    loopbackJson,
    getAppInfo,
    getImportReadiness,
    getCachedImportReadiness: () => importReadinessCache,
    getCachedCloudHalSettings: () => cloudHalSettingsCache,
    fetchHalImportGuard,
    evaluateHalQuery,
    evaluateHalQueryStream,
    pollShiftState,
    startShiftPolling,
    fetchClinicalContext,
    fetchStandingConsent,
    explainHalBlock,
    fetchHalSessionAudit,
    getCloudHalSettings,
    setCloudHalEnabled,
    getImportBundle,
    getImportSyncStatus,
    refreshImports,
    syncAccountingDocuments,
    listPracticeSourceCatalog,
    fetchPracticeSource,
    pullPracticeSources,
    getChartOfAccounts,
    draftJournalEntry,
    listPostingQueue,
    enqueueJournalPosting,
    reviewPostingQueueEntry,
    bulkReviewPostingQueue,
    exportApprovedPostingQueue,
    outboundPost,
    sendEmailWithConsent,
    exportPostingQueueIifWithConsent,
    buildClaimPacketWithConsent,
    exportNarrativePortalPrepWithConsent,
    postQboJournalWithConsent,
    buildPayerPortalRpaWithConsent,
    queueSoftdentWritebackWithConsent,
    softdentWritebackStatus,
    quickbooksOnlineStatus,
    listOutboundAudit,
    employeeStatus,
    listEmployeeWorkLog,
    appendEmployeeWorkLog,
    runEmployeeShift,
    webResearch,
    listHalMemories,
    rememberHalFact,
    rememberHalWebFindings,
    updateHalSessionContext,
    halLearningStatus,
    getTaxPlan,
    getIntegrationHealth,
    getAutomationRegistry,
    buildSupportBundle,
    getFinancialReports,
    getDailyCloseout,
    runProgramSelfHeal,
    getProgramHelp,
    grepProgramSource,
    readProgramFile,
    listProgramFiles,
    applyProgramPatch,
    runHalValidation,
    runNodeSyntaxCheck,
    semanticSearchProgram,
    runGitReadonly,
    runAllowlistedCommand,
    applyProgramPatches,
    showWorkstationMessagePopup,
    flushMessagePopups,
    setPopupStation,
    showWorkstationMainWindow,
    searchHalMemories,
    searchPayerReference,
    lookupFeeSchedule,
    listEligibilityCache,
    upsertEligibilityCache,
    searchEligibilityCache,
    fetchEligibility271,
    clearinghouseStatus,
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
  if (typeof DesktopBridge.startShiftPolling === "function") {
    DesktopBridge.whenReady(() => DesktopBridge.startShiftPolling(60000));
  }
}

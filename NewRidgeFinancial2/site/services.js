/**
 * Service / data layer for NewRidgeFinancial 2.0.
 *
 * Read paths use SoftDent / QuickBooks imports or empty shells.
 * Write paths (claims, narratives, documents) persist locally via the desktop bridge.
 */
const Services = (function () {
  const isNode = typeof window === "undefined";

  function resolveEmptyStates() {
    if (typeof EmptyStates !== "undefined") return EmptyStates;
    if (typeof window !== "undefined" && window.EmptyStates) return window.EmptyStates;
    try {
      return require("./empty-states.js");
    } catch {
      return { dashboard: () => null, store: () => ({}) };
    }
  }

  function primaryProvider() {
    return resolveEmptyStates().PRIMARY_PROVIDER || "Dr. Michael Reno";
  }

  function bridge() {
    if (typeof globalThis !== "undefined" && globalThis.DesktopBridge) return globalThis.DesktopBridge;
    if (typeof DesktopBridge !== "undefined") return DesktopBridge;
    if (typeof window !== "undefined" && window.DesktopBridge) return window.DesktopBridge;
    return null;
  }

  function delay(ms) {
    if (isNode) return Promise.resolve();
    if (typeof window !== "undefined" && !window.__NR2_SIMULATE_LATENCY__) return Promise.resolve();
    return new Promise((resolve) => setTimeout(resolve, ms || 220));
  }

  function clone(value) {
    return value == null ? value : JSON.parse(JSON.stringify(value));
  }

  function uid(prefix) {
    return `${prefix || "id"}-${Date.now().toString(36)}-${Math.floor(Math.random() * 1e4).toString(36)}`;
  }

  const mem = {};
  const KEY = (k) => `nr2:v2:${k}`;
  let importBundleCache = null;
  let importBundleAt = 0;
  const IMPORT_CACHE_TTL_MS = 30000;
  const SNAPSHOT_INVALIDATING_KEYS = new Set(["claims", "narratives", "documents", "library"]);

  function invalidateSnapshotForKey(key) {
    if (SNAPSHOT_INVALIDATING_KEYS.has(key) && typeof SnapshotStore !== "undefined") {
      SnapshotStore.invalidate(`local:${key}`);
    }
  }

  function resolveImportLoader() {
    if (typeof ImportLoader !== "undefined") return ImportLoader;
    if (typeof window !== "undefined" && window.ImportLoader) return window.ImportLoader;
    try {
      return require("./import-loader.js");
    } catch {
      return null;
    }
  }

  async function loadImportBundle(force) {
    const loader = resolveImportLoader();
    if (!loader || !loader.shouldLoadImports()) return null;
    const now = Date.now();
    if (force) {
      importBundleCache = null;
      importBundleAt = 0;
    }
    if (!force && importBundleCache && now - importBundleAt < IMPORT_CACHE_TTL_MS) {
      return importBundleCache;
    }
    try {
      importBundleCache = await loader.loadBundle(Boolean(force));
      importBundleAt = now;
      return importBundleCache;
    } catch (err) {
      if (typeof RuntimeIssues !== "undefined") RuntimeIssues.record("services.loadImportBundle", err);
      return null;
    }
  }

  async function waitForImportSync(br, maxMs) {
    if (!br || typeof br.getImportSyncStatus !== "function") return null;
    const deadline = Date.now() + (maxMs || 120000);
    let status = await br.getImportSyncStatus();
    while (status && status.status === "running" && Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 250));
      status = await br.getImportSyncStatus();
    }
    return status;
  }

  async function refreshImports(options) {
    const opts = options || {};
    const reason = opts.reason || "manual";
    const skipWait = reason === "boot" || reason === "background" || opts.waitForCompletion === false;
    const br = bridge();
    importBundleCache = null;
    importBundleAt = 0;
    try {
      if (br && typeof br.refreshImports === "function") {
        const kickoff = await br.refreshImports();
        if (kickoff && kickoff.status === "running") {
          if (!skipWait) {
            const finalStatus = await waitForImportSync(br, opts.maxWaitMs || 120000);
            if (finalStatus && finalStatus.status === "failed") {
              const err = new Error(finalStatus.error || "Import sync failed");
              if (typeof RuntimeIssues !== "undefined") RuntimeIssues.record("services.refreshImports", err, finalStatus);
            } else if (finalStatus && finalStatus.result && finalStatus.result.documents) {
              applySyncedDocumentsState(finalStatus.result.documents);
            }
          } else {
            const bundle = await loadImportBundle(false);
            if (bundle) {
              return Object.assign({}, bundle, {
                syncStatus: Object.assign({}, bundle.syncStatus || {}, { status: "running", attempted: true }),
              });
            }
            return {
              loadedAt: new Date().toISOString(),
              softdent: {},
              quickbooks: {},
              syncStatus: { status: "running", attempted: true },
            };
          }
        } else if (kickoff && kickoff.status === "failed") {
          const err = new Error(kickoff.error || "Import sync failed");
          if (typeof RuntimeIssues !== "undefined") RuntimeIssues.record("services.refreshImports", err, kickoff);
        }
      }
      return await loadImportBundle(true);
    } catch (err) {
      if (typeof RuntimeIssues !== "undefined") RuntimeIssues.record("services.refreshImports", err, opts);
      throw err;
    }
  }

  async function pullPracticeSources(options) {
    const opts = options || {};
    const br = bridge();
    importBundleCache = null;
    importBundleAt = 0;
    if (!br || typeof br.pullPracticeSources !== "function") {
      const err = new Error("Practice source pull requires the NR2 desktop app.");
      if (typeof RuntimeIssues !== "undefined") RuntimeIssues.record("services.pullPracticeSources", err);
      throw err;
    }
    try {
      const result = await br.pullPracticeSources({ fullPull: Boolean(opts.fullPull) });
      if (result && result.documents && result.documents.state) {
        applySyncedDocumentsState(result.documents);
      } else if (typeof br.syncAccountingDocuments === "function") {
        await ensureDocumentsSynced();
      }
      importBundleCache = null;
      importBundleAt = 0;
      if (typeof SnapshotStore !== "undefined") SnapshotStore.invalidate("practice-source-pull");
      return result;
    } catch (err) {
      if (typeof RuntimeIssues !== "undefined") RuntimeIssues.record("services.pullPracticeSources", err, opts);
      throw err;
    }
  }

  function buildDashboardsFromBundle(bundle) {
    const loader = resolveImportLoader();
    const empty = resolveEmptyStates();
    const pageIds = ["financial", "softdent", "quickbooks", "ar", "practice"];
    const dashboards = {};
    pageIds.forEach((pageId) => {
      if (loader && bundle && typeof loader.buildDashboard === "function") {
        dashboards[pageId] = clone(loader.buildDashboard(pageId, bundle) || empty.dashboard(pageId));
      } else {
        dashboards[pageId] = clone(empty.dashboard(pageId));
      }
    });
    return dashboards;
  }

  async function load(key, emptyFn) {
    if (mem[key]) return mem[key];
    const br = bridge();
    if (br) {
      try {
        const saved = await br.storageGet(KEY(key));
        if (saved) {
          mem[key] = saved;
          return saved;
        }
      } catch {
        /* fall through */
      }
      if (br.hasDesktopApi && br.hasDesktopApi()) {
        // Desktop store may not be readable yet; do not cache an empty shell.
        return emptyFn();
      }
    }
    const initial = emptyFn();
    mem[key] = initial;
    if (br) {
      try {
        await br.storageSet(KEY(key), initial);
      } catch {
        /* persistence optional */
      }
    }
    return initial;
  }

  async function save(key, value) {
    mem[key] = value;
    invalidateSnapshotForKey(key);
    const br = bridge();
    if (br) {
      try {
        await br.storageSet(KEY(key), value);
      } catch {
        /* persistence optional */
      }
    }
    return value;
  }

  /* ============ Dashboards (read paths) ============ */

  async function readDashboard(pageId) {
    await delay(180);
    if (typeof SnapshotStore !== "undefined") {
      const cached = SnapshotStore.peek();
      if (cached && cached.dashboards && cached.dashboards[pageId]) {
        return clone(cached.dashboards[pageId]);
      }
    }
    const loader = resolveImportLoader();
    const bundle = await loadImportBundle(false);
    if (loader && typeof loader.buildDashboard === "function") {
      return clone(loader.buildDashboard(pageId, bundle));
    }
    const empty = resolveEmptyStates();
    const data = empty.dashboard(pageId);
    if (!data) {
      const err = new Error(`No data source configured for ${pageId}`);
      err.code = "NO_DATA";
      throw err;
    }
    return clone(data);
  }

  async function readOfficeTasks() {
    if (typeof OfficeTaskStore !== "undefined") {
      return OfficeTaskStore.list();
    }
    const desktop = bridge();
    if (desktop && typeof desktop.storageGet === "function") {
      try {
        return (await desktop.storageGet("halOfficeTasks")) || [];
      } catch (err) {
        if (typeof RuntimeIssues !== "undefined") RuntimeIssues.record("services.readOfficeTasks", err);
        return [];
      }
    }
    return [];
  }

  async function buildProgramSnapshotCore() {
    await delay(120);
    const safe = async (fn) => {
      try {
        return await fn();
      } catch (err) {
        if (typeof RuntimeIssues !== "undefined") RuntimeIssues.record("services.readProgramSnapshot", err);
        return null;
      }
    };
    const loader = resolveImportLoader();
    const bundle = await loadImportBundle(false);
    const dashboards = buildDashboardsFromBundle(bundle);
    const [claimsState, narrativesState, documentsState, libraryState, officeTasks] = await Promise.all([
      safe(() => claims.list()),
      safe(() => narratives.getState()),
      safe(() => documents.list({})),
      safe(() => library.search("")),
      safe(() => readOfficeTasks()),
    ]);
    const claimsByStatus = {};
    (claimsState?.claims || []).forEach((claim) => {
      const key = claim.status || "Unknown";
      claimsByStatus[key] = (claimsByStatus[key] || 0) + 1;
    });
    const usingImports = Boolean(loader && bundle && loader.hasImportData(bundle));
    const desktop = bridge();
    const officeTasksSourceAvailable =
      typeof OfficeTaskStore !== "undefined"
        ? OfficeTaskStore.isConfigured()
        : Boolean(desktop && typeof desktop.storageGet === "function");
    const runtimeIssues =
      typeof RuntimeIssues !== "undefined" ? RuntimeIssues.list().slice(0, 8) : [];
    return {
      gatheredAt: new Date().toISOString(),
      label: usingImports
        ? "Local program snapshot (SoftDent/QuickBooks imports + persisted data)"
        : "Local program snapshot (imports unavailable — empty or persisted local data only)",
      importBundle: bundle
        ? {
            loadedAt: bundle.loadedAt,
            syncStatus: bundle.syncStatus || null,
            diagnostics: bundle.diagnostics || null,
            softdent: bundle.softdent,
            quickbooks: bundle.quickbooks,
            softdentDir: bundle.softdent?.dir,
            quickbooksDir: bundle.quickbooks?.dir,
          }
        : null,
      dashboards: {
        financial: dashboards.financial,
        softdent: dashboards.softdent,
        quickbooks: dashboards.quickbooks,
        ar: dashboards.ar,
        practice: dashboards.practice,
      },
      claims: claimsState
        ? {
            total: claimsState.claims.length,
            claims: claimsState.claims || [],
            byStatus: claimsByStatus,
            laneTotals: claimsState.laneTotals || {},
            kpis: claimsState.kpis || [],
            readiness: claimsState.readiness || null,
            safety: claimsState.safety || null,
            top: (claimsState.claims || []).slice(0, 10),
          }
        : null,
      narratives: narrativesState
        ? {
            drafts: (narrativesState.drafts || []).length,
            latest: (narrativesState.drafts || []).find((d) => d.latest) || (narrativesState.drafts || [])[0] || null,
            focus: narrativesState.composer?.focus || "",
          }
        : null,
      documents: documentsState
        ? (() => {
            const summary = summarizeDocumentQueueForHal(documentsState.queue || []);
            return {
              entity: documentsState.entity,
              queueCount: (documentsState.queue || []).length,
              posting: documentsState.posting || [],
              period: documentsState.period || null,
              sourceCounts: summary.sourceCounts,
              top: summary.top,
              workbookSample: summary.workbookSample,
            };
          })()
        : null,
      library: libraryState
        ? {
            results: libraryState.results,
            storage: libraryState.storage || {},
            top: (libraryState.docs || []).slice(0, 8),
            docs: libraryState.docs || [],
          }
        : null,
      officeTasks: officeTasks || [],
      officeTasksState: officeTasksSourceAvailable ? (officeTasks && officeTasks.length ? "loaded" : "empty") : "not_configured",
      runtimeIssues,
    };
  }

  async function readProgramSnapshot() {
    if (typeof SnapshotStore !== "undefined") {
      return SnapshotStore.get(() => buildProgramSnapshotCore());
    }
    return buildProgramSnapshotCore();
  }

  /* ============ Claims ============ */

  function emptyClaims() {
    return clone(resolveEmptyStates().store("claims"));
  }

  function claimsImportActive(bundle) {
    return Boolean(bundle && bundle.softdent && bundle.softdent.claims && bundle.softdent.claims.rows && bundle.softdent.claims.rows.length);
  }

  const claims = {
    async list() {
      await delay();
      const loader = resolveImportLoader();
      const bundle = await loadImportBundle(false);
      if (loader && claimsImportActive(bundle)) {
        const merged = clone(loader.mergeClaimsState(emptyClaims(), bundle));
        merged.claimsMode = "import-readonly";
        merged.safety = "Import read-only · payer submission locked.";
        return merged;
      }
      const local = clone(await load("claims", emptyClaims));
      local.claimsMode = "local-workbench";
      return local;
    },
    async get(id) {
      const loader = resolveImportLoader();
      const bundle = await loadImportBundle(false);
      if (loader && claimsImportActive(bundle)) {
        const state = loader.mergeClaimsState(emptyClaims(), bundle);
        const claim = (state.claims || []).find((c) => c.id === id) || null;
        const detail =
          (state.detailById || {})[id] ||
          (claim
            ? {
                id: claim.id,
                patient: claim.patient,
                dob: claim.dob,
                age: "—",
                insurance: claim.payer || "—",
                billed: claim.amount,
                dos: claim.serviceDate || "—",
                procedure: claim.procedure,
                code: claim.procedure,
                provider: primaryProvider(),
                npi: "—",
                validation: 0,
                alert: "SoftDent import read-only · edits disabled.",
              }
            : null);
        return clone({ claim, detail, claimsMode: "import-readonly" });
      }
      const state = await load("claims", emptyClaims);
      const claim = (state.claims || []).find((c) => c.id === id) || null;
      const detail =
        (state.detailById || {})[id] ||
        (claim
          ? {
              id: claim.id,
              patient: claim.patient,
              dob: claim.dob,
              age: "—",
              insurance: claim.payer || "—",
              billed: claim.amount,
              dos: claim.serviceDate || "—",
              procedure: claim.procedure,
              code: claim.procedure,
              provider: primaryProvider(),
              npi: "—",
              validation: 0,
              alert: "Local workbench only · payer submission locked.",
            }
          : null);
      return clone({ claim, detail });
    },
    async updateStatus(id, status) {
      await delay(160);
      const bundle = await loadImportBundle(false);
      if (claimsImportActive(bundle)) {
        throw new Error("Claims are read-only while SoftDent claims import is active.");
      }
      const state = clone(await load("claims", emptyClaims));
      const claim = (state.claims || []).find((c) => c.id === id);
      if (!claim) throw new Error("Claim not found");
      claim.status = status;
      await save("claims", state);
      return clone(claim);
    },
    async remove(id) {
      await delay(160);
      const bundle = await loadImportBundle(false);
      if (claimsImportActive(bundle)) {
        throw new Error("Claims are read-only while SoftDent claims import is active.");
      }
      const state = clone(await load("claims", emptyClaims));
      const before = state.claims.length;
      state.claims = state.claims.filter((c) => c.id !== id);
      if (state.claims.length === before) throw new Error("Claim not found");
      await save("claims", state);
      return true;
    },
    async create(data) {
      await delay(160);
      const bundle = await loadImportBundle(false);
      if (claimsImportActive(bundle)) {
        throw new Error("Claims are read-only while SoftDent claims import is active.");
      }
      const state = clone(await load("claims", emptyClaims));
      const claim = Object.assign(
        { id: uid("CLM"), status: "Draft", patient: "New Patient", dob: "—", procedure: "—", amount: "$0.00", age: "just now" },
        data || {},
      );
      state.claims.unshift(claim);
      await save("claims", state);
      return clone(claim);
    },
  };

  /* ============ Narratives ============ */

  function emptyNarratives() {
    return clone(resolveEmptyStates().store("narratives"));
  }

  function composeNarrative(payload) {
    const points = (payload.keyPoints || []).filter(Boolean);
    const lead =
      payload.focus === "Medical Necessity"
        ? "The following findings establish medical necessity for the proposed treatment."
        : `Clinical summary (${payload.focus || "general"}).`;
    const body = points.map((p) => p.replace(/\.$/, "") + ".").join(" ");
    const closing =
      payload.length === "Brief"
        ? "Treatment is recommended."
        : "Based on the above, the proposed procedure is the appropriate and medically necessary course of treatment, and is consistent with accepted dental standards of care.";
    return [lead, body, closing].filter(Boolean).join(" ");
  }

  const narratives = {
    async getState() {
      await delay();
      return clone(await load("narratives", emptyNarratives));
    },
    async generate(payload) {
      await delay(420);
      const claim = payload && payload.claim;
      const lib = typeof HalNarrativeLibrary !== "undefined" ? HalNarrativeLibrary : null;
      if (claim && lib && typeof lib.selectBestNarrativeForClaim === "function") {
        const selection = lib.selectBestNarrativeForClaim(claim);
        if (selection && selection.selected && selection.selected.text) return selection.selected.text;
      }
      return composeNarrative(payload || {});
    },
    async saveDraft(payload) {
      await delay(200);
      const state = clone(await load("narratives", emptyNarratives));
      const nextNum = state.drafts.length + 1;
      state.drafts.forEach((d) => (d.latest = false));
      const draft = {
        version: `v${nextNum}`,
        latest: true,
        modified: new Date().toLocaleString(),
        points: (payload.keyPoints || []).length,
        length: payload.length || "Standard",
        focus: payload.focus || "Medical Necessity",
        by: "New Ridge Owner",
        text: payload.text || "",
        keyPoints: (payload.keyPoints || []).slice(),
      };
      state.drafts.unshift(draft);
      state.composer = {
        tone: payload.tone || state.composer.tone,
        length: payload.length || state.composer.length,
        focus: payload.focus || state.composer.focus,
        keyPoints: (payload.keyPoints || []).slice(),
        context: payload.context || "",
      };
      if (payload.text) state.draftText = payload.text;
      await save("narratives", state);
      return clone(state);
    },
    async deleteDraft(version) {
      await delay(160);
      const state = clone(await load("narratives", emptyNarratives));
      state.drafts = state.drafts.filter((d) => d.version !== version);
      if (state.drafts.length && !state.drafts.some((d) => d.latest)) state.drafts[0].latest = true;
      await save("narratives", state);
      return clone(state);
    },
  };

  /* ============ Documents ============ */

  function emptyDocuments() {
    return clone(resolveEmptyStates().store("documents"));
  }

  function recomputePosting(queue) {
    const groups = { "Pending Review": { tone: "warn" }, "Ready to Post": { tone: "ok" }, Posted: { tone: "info" } };
    const out = Object.entries(groups).map(([label, meta]) => ({
      label,
      tone: meta.tone,
      count: queue.filter((q) => q.status === label).length,
    }));
    out.push({ label: "Total Documents", tone: "muted", count: queue.length, amount: "All Time" });
    return out;
  }

  function parseMoney(value) {
    const amount = Number(String(value || "").replace(/[^0-9.-]/g, ""));
    return Number.isFinite(amount) ? amount : 0;
  }

  function formatMoney(value) {
    const amount = parseMoney(value);
    if (!amount) return "—";
    return amount.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  }

  function recomputeDocumentPeriod(queue) {
    const total = (queue || []).reduce((acc, doc) => acc + parseMoney(doc.amount), 0);
    const posted = (queue || []).filter((doc) => doc.status === "Posted").reduce((acc, doc) => acc + parseMoney(doc.amount), 0);
    const pending = Math.max(0, total - posted);
    const ready = (queue || []).filter((doc) => doc.status === "Ready to Post").length;
    const postedCount = (queue || []).filter((doc) => doc.status === "Posted").length;
    const count = (queue || []).length || 0;
    return {
      label: new Date().toISOString().slice(0, 7),
      documents: count,
      totalAmount: formatMoney(total),
      postedAmount: formatMoney(posted),
      pendingAmount: formatMoney(pending),
      reviewedPct: count ? Math.round(((postedCount + ready) / count) * 100) : 0,
      postedPct: count ? Math.round((postedCount / count) * 100) : 0,
      pendingPct: count ? Math.round(((queue || []).filter((doc) => doc.status === "Pending Review").length / count) * 100) : 0,
      readyPct: count ? Math.round((ready / count) * 100) : 0,
    };
  }

  function documentAgeDays(dateValue) {
    const then = Date.parse(dateValue);
    if (!Number.isFinite(then)) return 0;
    return Math.max(0, Math.round((Date.now() - then) / 86400000));
  }

  function classifyDocumentSource(doc) {
    const system = String((doc && doc.sourceSystem) || "").trim().toLowerCase();
    if (system === "quickbooks" || system === "softdent") return system;
    if (doc && doc.autoImported) return "ocr";
    return "manual";
  }

  function summarizeDocumentQueueForHal(queue) {
    const list = Array.isArray(queue) ? queue : [];
    const sourceCounts = { quickbooks: 0, softdent: 0, ocr: 0, manual: 0 };
    list.forEach((doc) => {
      sourceCounts[classifyDocumentSource(doc)] += 1;
    });
    const top = [];
    const seenSources = new Set();
    list.forEach((doc) => {
      const source = classifyDocumentSource(doc);
      if (!seenSources.has(source) && top.length < 8) {
        seenSources.add(source);
        top.push(doc);
      }
    });
    list.forEach((doc) => {
      if (top.length >= 8) return;
      if (!top.some((item) => item.id === doc.id)) top.push(doc);
    });
    const workbookSample = list.slice(0, 20).map((doc) => ({
      id: doc.id,
      vendor: doc.vendor,
      type: doc.type,
      date: doc.date,
      amount: doc.amount,
      status: doc.status,
      age: doc.age,
      autoImported: doc.autoImported,
      sourceSystem: doc.sourceSystem || classifyDocumentSource(doc),
      sourceFile: doc.sourceFile || null,
    }));
    return { sourceCounts, top, workbookSample };
  }

  function applySyncedDocumentsState(syncResult) {
    if (!syncResult || typeof syncResult !== "object") return;
    const state = syncResult.state;
    if (!state || typeof state !== "object") return;
    mem.documents = state;
    notifyDocumentsSynced(syncResult);
  }

  function notifyDocumentsSynced(result) {
    if (typeof window === "undefined" || typeof window.dispatchEvent !== "function") return;
    const state = (result && result.state) || mem.documents || null;
    const queueCount = state && Array.isArray(state.queue) ? state.queue.length : (result && result.queueCount) || 0;
    try {
      window.dispatchEvent(
        new CustomEvent("nr2:documents-synced", {
          detail: { queueCount, syncedAt: (result && result.syncedAt) || new Date().toISOString() },
        }),
      );
    } catch {
      /* event dispatch optional */
    }
  }

  async function ensureDocumentsSynced() {
    const br = bridge();
    if (!br || typeof br.syncAccountingDocuments !== "function") return;
    try {
      const result = await br.syncAccountingDocuments();
      if (result && result.state && typeof result.state === "object") {
        applySyncedDocumentsState(result);
        return;
      }
      delete mem.documents;
      notifyDocumentsSynced(result);
    } catch (err) {
      if (typeof RuntimeIssues !== "undefined") RuntimeIssues.record("services.ensureDocumentsSynced", err);
    }
  }

  const documents = {
    async list(filter) {
      await ensureDocumentsSynced();
      await delay();
      const state = clone(await load("documents", emptyDocuments));
      let queue = state.queue;
      if (filter && filter.query) {
        const q = filter.query.toLowerCase();
        queue = queue.filter((d) => `${d.id} ${d.type} ${d.vendor}`.toLowerCase().includes(q));
      }
      if (filter && filter.status && filter.status !== "All") {
        queue = queue.filter((d) => d.status === filter.status);
      }
      return clone({ entity: state.entity, queue, posting: recomputePosting(state.queue), period: state.period });
    },
    async get(id) {
      const state = await load("documents", emptyDocuments);
      const doc = (state.queue || []).find((d) => d.id === id) || null;
      const preview =
        (state.previewById || {})[id] ||
        (doc
          ? { vendor: (doc.vendor || "").toUpperCase(), invoice: doc.id, date: doc.date, total: doc.amount, file: `${doc.id}.pdf`, pages: "1 of 1", uploaded: doc.date }
          : null);
      return clone({ doc, preview });
    },
    async add(input) {
      await delay(160);
      const state = clone(await load("documents", emptyDocuments));
      const payload = input || {};
      const id = String(payload.id || uid("DOC")).trim();
      const status = payload.status || "Pending Review";
      const date = payload.date || new Date().toISOString().slice(0, 10);
      const doc = {
        id,
        type: payload.type || "Accounting Document",
        vendor: payload.vendor || "Unassigned Vendor",
        date,
        amount: payload.amount ? formatMoney(payload.amount) : "—",
        status,
        statusTone: status === "Posted" ? "info" : status === "Ready to Post" ? "ok" : "warn",
        age: documentAgeDays(date),
      };
      state.queue = [doc].concat(state.queue || []);
      state.previewById = Object.assign({}, state.previewById || {}, {
        [id]: {
          vendor: doc.vendor.toUpperCase(),
          invoice: id,
          date: doc.date,
          total: doc.amount,
          file: payload.fileName || `${id}.pdf`,
          pages: payload.pages || "1 of 1",
          uploaded: new Date().toISOString().slice(0, 10),
        },
      });
      state.entity = state.entity || "New Ridge Family Financial";
      state.period = recomputeDocumentPeriod(state.queue);
      await save("documents", state);
      return clone(doc);
    },
    async updateStatus(id, status) {
      await delay(160);
      const state = clone(await load("documents", emptyDocuments));
      const doc = (state.queue || []).find((d) => d.id === id);
      if (!doc) throw new Error("Document not found");
      doc.status = status;
      doc.statusTone = status === "Posted" ? "info" : status === "Ready to Post" ? "ok" : "warn";
      state.period = recomputeDocumentPeriod(state.queue);
      await save("documents", state);
      return clone(doc);
    },
    async remove(id) {
      await delay(160);
      const state = clone(await load("documents", emptyDocuments));
      state.queue = state.queue.filter((d) => d.id !== id);
      state.period = recomputeDocumentPeriod(state.queue);
      await save("documents", state);
      return true;
    },
  };

  /* ============ Library ============ */

  function emptyLibrary() {
    return clone(resolveEmptyStates().store("library"));
  }

  const library = {
    async search(query, filters) {
      await delay();
      const state = clone(await load("library", emptyLibrary));
      let docs = state.docs;
      if (query) {
        const q = query.toLowerCase();
        docs = docs.filter((d) => `${d.title} ${(d.tags || []).join(" ")} ${d.type}`.toLowerCase().includes(q));
      }
      if (filters && filters.type && filters.type !== "All") {
        docs = docs.filter((d) => d.type === filters.type);
      }
      return clone({ results: docs.length, storage: state.storage, filters: state.filters, docs });
    },
    async get(title) {
      const state = await load("library", emptyLibrary);
      const doc = (state.docs || []).find((d) => d.title === title) || null;
      const detail =
        (state.detailById || {})[title] ||
        (doc
          ? { title: doc.title, type: doc.type, size: doc.size, updated: doc.updated, docType: doc.type, tags: doc.tags || [], uploadedBy: doc.by, dateAdded: doc.updated, path: `/library/${doc.title.toLowerCase().replace(/\s+/g, "-")}.${(doc.type || "pdf").toLowerCase()}` }
          : null);
      return clone({ doc, detail });
    },
  };

  /* ============ Office Manager ============ */

  const officeManager = {
    async surfaces(halData) {
      await delay();
      const items = ((halData && halData.workSurfaces && halData.workSurfaces.items) || []).map((item) => {
        const reg = ((halData && halData.registry) || []).find((r) => r.id === item.target) || {};
        return { label: item.label, target: item.target, state: reg.state || "unknown", detail: item.detail || reg.purpose || "", nextAction: reg.nextAction || "" };
      });
      return items;
    },
    async consoleState(halData) {
      await delay();
      const runtime = (halData && halData.runtime) || {};
      if (runtime.officeManager) return runtime.officeManager;
      const officeApi =
        typeof HalOfficeManager !== "undefined"
          ? HalOfficeManager
          : typeof globalThis !== "undefined" && globalThis.HalOfficeManager
            ? globalThis.HalOfficeManager
            : null;
      if (!officeApi) return null;
      try {
        const snap = await readProgramSnapshot();
        return officeApi.buildOfficeManagerState(snap, {}, null);
      } catch {
        return null;
      }
    },
  };

  async function resetAll() {
    Object.keys(mem).forEach((k) => delete mem[k]);
    const br = bridge();
    if (br) {
      for (const k of ["claims", "narratives", "documents", "library"]) {
        try {
          await br.storageSet(KEY(k), null);
        } catch {
          /* ignore */
        }
      }
    }
  }

  return {
    readDashboard,
    readProgramSnapshot,
    buildProgramSnapshotCore,
    buildDashboardsFromBundle,
    loadImportBundle,
    refreshImports,
    pullPracticeSources,
    invalidateSnapshot: () => {
      if (typeof SnapshotStore !== "undefined") SnapshotStore.invalidate("services");
    },
    claims,
    narratives,
    documents,
    library,
    officeManager,
    composeNarrative,
    resetAll,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = Services;
}
if (typeof window !== "undefined") {
  window.Services = Services;
}
if (typeof globalThis !== "undefined") {
  globalThis.Services = Services;
}

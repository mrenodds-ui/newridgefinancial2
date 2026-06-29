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
    if (typeof DesktopBridge !== "undefined") return DesktopBridge;
    if (typeof window !== "undefined" && window.DesktopBridge) return window.DesktopBridge;
    return null;
  }

  function delay(ms) {
    if (isNode) return Promise.resolve();
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
    } catch {
      return null;
    }
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

  async function readProgramSnapshot() {
    await delay(120);
    const safe = async (fn) => {
      try {
        return await fn();
      } catch {
        return null;
      }
    };
    const [financial, softdent, quickbooks, ar, claimsState, narrativesState, documentsState, libraryState] = await Promise.all([
      safe(() => readDashboard("financial")),
      safe(() => readDashboard("softdent")),
      safe(() => readDashboard("quickbooks")),
      safe(() => readDashboard("ar")),
      safe(() => claims.list()),
      safe(() => narratives.getState()),
      safe(() => documents.list({})),
      safe(() => library.search("")),
    ]);
    const claimsByStatus = {};
    (claimsState?.claims || []).forEach((claim) => {
      const key = claim.status || "Unknown";
      claimsByStatus[key] = (claimsByStatus[key] || 0) + 1;
    });
    const loader = resolveImportLoader();
    const bundle = await loadImportBundle(false);
    const usingImports = Boolean(loader && bundle && loader.hasImportData(bundle));
    return {
      gatheredAt: new Date().toISOString(),
      label: usingImports
        ? "Local program snapshot (SoftDent/QuickBooks imports + persisted data)"
        : "Local program snapshot (imports unavailable — empty or persisted local data only)",
      importBundle: bundle
        ? {
            loadedAt: bundle.loadedAt,
            syncStatus: bundle.syncStatus || null,
            softdent: bundle.softdent,
            quickbooks: bundle.quickbooks,
            softdentDir: bundle.softdent?.dir,
            quickbooksDir: bundle.quickbooks?.dir,
          }
        : null,
      dashboards: { financial, softdent, quickbooks, ar },
      claims: claimsState
        ? {
            total: claimsState.claims.length,
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
        ? {
            entity: documentsState.entity,
            queueCount: (documentsState.queue || []).length,
            posting: documentsState.posting || [],
            period: documentsState.period || null,
            top: (documentsState.queue || []).slice(0, 8),
          }
        : null,
      library: libraryState
        ? {
            results: libraryState.results,
            storage: libraryState.storage || {},
            top: (libraryState.docs || []).slice(0, 8),
            docs: libraryState.docs || [],
          }
        : null,
      officeTasks: [],
    };
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

  const documents = {
    async list(filter) {
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
    async updateStatus(id, status) {
      await delay(160);
      const state = clone(await load("documents", emptyDocuments));
      const doc = (state.queue || []).find((d) => d.id === id);
      if (!doc) throw new Error("Document not found");
      doc.status = status;
      doc.statusTone = status === "Posted" ? "info" : status === "Ready to Post" ? "ok" : "warn";
      await save("documents", state);
      return clone(doc);
    },
    async remove(id) {
      await delay(160);
      const state = clone(await load("documents", emptyDocuments));
      state.queue = state.queue.filter((d) => d.id !== id);
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
    loadImportBundle,
    refreshImports: () => loadImportBundle(true),
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

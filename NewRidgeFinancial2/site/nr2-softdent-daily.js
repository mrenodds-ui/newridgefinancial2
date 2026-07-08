/**
 * SoftDent daily widgets (browser) — live /api/softdent/* when loopback is up, else import snapshot.
 */
const NR2SoftdentDaily = (function () {
  const LIVE_ENDPOINTS = {
    collectionsDaily: "/api/softdent/collections-daily",
    newPatientsMtd: "/api/softdent/new-patients-mtd",
    appointmentsSnapshot: "/api/softdent/appointments-snapshot",
    claimsOutstanding: "/api/softdent/claims-outstanding",
    providerProduction: "/api/softdent/provider-production",
    adjustmentLog: "/api/softdent/adjustment-log",
    patientRetention: "/api/softdent/patient-retention",
    operatoryGrid: "/api/softdent/operatory-grid",
  };
  const LIVE_TTL_MS = 60000;

  let liveCache = {};
  let liveFetchedAt = 0;
  let livePrefetchPromise = null;

  function parseMoney(value) {
    const n = Number(String(value || "0").replace(/[$,]/g, ""));
    return Number.isFinite(n) ? n : 0;
  }

  function analyticsApi() {
    return typeof NR2Analytics !== "undefined" ? NR2Analytics : null;
  }

  function loopbackBase() {
    if (typeof window === "undefined" || !window.location) return null;
    const port = window.NR2_LOOPBACK_PORT || window.location.port || "8765";
    const host = window.location.hostname || "127.0.0.1";
    const protocol = window.location.protocol || "http:";
    return `${protocol}//${host}:${port}`;
  }

  function isLoopbackHost() {
    if (typeof window === "undefined" || !window.location) return false;
    const host = (window.location.hostname || "").toLowerCase();
    return host === "127.0.0.1" || host === "localhost" || host === "::1";
  }

  async function fetchJson(path) {
    const br = typeof window !== "undefined" && window.pywebview && window.pywebview.api;
    if (br && typeof br.loopbackJson === "function") {
      try {
        return await br.loopbackJson(path, { method: "GET" });
      } catch {
        return null;
      }
    }
    if (typeof fetch !== "function" || !isLoopbackHost()) return null;
    const base = loopbackBase();
    if (!base) return null;
    try {
      const res = await fetch(`${base}${path}`, { method: "GET", cache: "no-store" });
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  }

  function useLive(key) {
    if (!liveCache[key] || Date.now() - liveFetchedAt > LIVE_TTL_MS) return null;
    return liveCache[key];
  }

  function clearLiveCache() {
    liveCache = {};
    liveFetchedAt = 0;
    livePrefetchPromise = null;
  }

  async function prefetchLive() {
    if (livePrefetchPromise) return livePrefetchPromise;
    livePrefetchPromise = (async () => {
      const pairs = await Promise.all(
        Object.entries(LIVE_ENDPOINTS).map(async ([key, path]) => [key, await fetchJson(path)]),
      );
      const next = {};
      pairs.forEach(([key, data]) => {
        if (data && typeof data === "object") next[key] = data;
      });
      if (Object.keys(next).length) {
        liveCache = next;
        liveFetchedAt = Date.now();
      }
      return liveCache;
    })().finally(() => {
      livePrefetchPromise = null;
    });
    return livePrefetchPromise;
  }

  function bundleFromSnapshot(snapshot) {
    return (snapshot && snapshot.importBundle) || null;
  }

  function claimsRows(snapshot) {
    const bundle = bundleFromSnapshot(snapshot);
    const claims = bundle && bundle.softdent && bundle.softdent.claims;
    if (!claims) return [];
    if (Array.isArray(claims)) return claims;
    if (Array.isArray(claims.rows)) return claims.rows;
    return [];
  }

  function collectionsDaily(snapshot) {
    const live = useLive("collectionsDaily");
    if (live) return live;
    const A = analyticsApi();
    if (!A) return { hasData: false, labels: [], values: [] };
    const bundle = bundleFromSnapshot(snapshot);
    if (bundle && bundle.softdent && bundle.softdent.dashboard) {
      const rows = Array.isArray(bundle.softdent.dashboard) ? bundle.softdent.dashboard : bundle.softdent.dashboard.rows || [];
      return {
        hasData: rows.some((row) => Number(row.collections || row.Collections) > 0),
        labels: rows.map((row) => String(row.period || row.Period || "")).filter(Boolean),
        values: rows.map((row) => Number(row.collections || row.Collections || 0)),
        source: "dashboard-monthly",
      };
    }
    return { hasData: false, labels: [], values: [], source: "none" };
  }

  function newPatientsMtd(snapshot) {
    const live = useLive("newPatientsMtd");
    if (live) return live;
    const dash = snapshot && snapshot.dashboards && snapshot.dashboards.practice;
    const count = dash && dash.newPatients && dash.newPatients.count;
    if (count != null) {
      return { hasData: true, count: Number(count), period: (dash.newPatients.period || "").slice(0, 7) };
    }
    const bundle = bundleFromSnapshot(snapshot);
    const np = bundle && bundle.softdent && bundle.softdent.newPatients;
    const rows = np && (np.rows || np);
    if (Array.isArray(rows) && rows.length) {
      const latest = rows[rows.length - 1];
      return {
        hasData: true,
        count: Number(latest.Count || latest.count || 0),
        period: String(latest.Period || latest.period || ""),
      };
    }
    return { hasData: false, count: 0 };
  }

  function appointmentsSnapshot(snapshot) {
    const live = useLive("appointmentsSnapshot");
    if (live) return live;
    const practice = snapshot && snapshot.dashboards && snapshot.dashboards.practice;
    const chairs = (practice && practice.operatoryChairs) || [];
    const appointments = chairs.slice(0, 12).map((chair) => ({
      date: chair.time || chair.start || "Today",
      patientId: chair.patient || chair.patientName || "—",
      provider: chair.provider || chair.providerName || "—",
      status: chair.status || "scheduled",
    }));
    return { hasData: appointments.length > 0, appointments };
  }

  function claimsOutstanding(snapshot) {
    const live = useLive("claimsOutstanding");
    if (live) return live;
    const rows = claimsRows(snapshot);
    const claims = rows
      .map((row) => ({
        claimId: String(row.ClaimId || row.claim_id || row.id || ""),
        patientName: String(row.PatientName || row.patient_name || ""),
        payer: String(row.Payer || row.payer || ""),
        serviceDate: String(row.ServiceDate || row.service_date || ""),
        amount: Number(String(row.ClaimAmount || row.amount || "0").replace(/[$,]/g, "")) || 0,
        status: String(row.ClaimStatus || row.status || ""),
      }))
      .filter((row) => row.claimId && row.amount > 0);
    const total = claims.reduce((acc, row) => acc + row.amount, 0);
    return { hasData: claims.length > 0, claims: claims.slice(0, 10), totalOutstanding: Math.round(total) };
  }

  function providerProduction(snapshot) {
    const live = useLive("providerProduction");
    if (live) return live;
    const fin = snapshot && snapshot.dashboards && snapshot.dashboards.financial;
    const providers = (fin && fin.providers && fin.providers.rows) || [];
    const mapped = providers.map((row) => ({
      providerCode: String(row.name || row.provider || ""),
      production: parseMoney(row.amount || row.production),
    }));
    const total = mapped.reduce((acc, row) => acc + row.production, 0);
    return { hasData: mapped.length > 0, providers: mapped, total: Math.round(total) };
  }

  function adjustmentLog(snapshot) {
    const live = useLive("adjustmentLog");
    if (live) return live;
    const bundle = bundleFromSnapshot(snapshot);
    const ar = bundle && bundle.softdent && bundle.softdent.ar;
    const rows = ar && (ar.rows || ar);
    if (Array.isArray(rows) && rows.length) {
      const adjustments = rows.slice(0, 10).map((row) => ({
        date: String(row.Period || row.period || row.date || ""),
        patientId: String(row.PatientId || row.patient_id || ""),
        code: String(row.Code || row.code || "AR"),
        amount: parseMoney(row.Amount || row.amount || row.Balance),
        description: String(row.Description || row.description || row.Aging || "A/R"),
      }));
      return { hasData: true, adjustments, source: "softdent.ar" };
    }
    return { hasData: false, adjustments: [] };
  }

  function patientRetention(snapshot) {
    const live = useLive("patientRetention");
    if (live) return live;
    const practice = snapshot && snapshot.dashboards && snapshot.dashboards.practice;
    const active = Number(practice && practice.patientCount) || 0;
    return { hasData: active > 0, activePatients: active, returningRatePct: null };
  }

  function operatoryGrid(snapshot) {
    const live = useLive("operatoryGrid");
    if (live && Array.isArray(live.operatoryChairs) && live.operatoryChairs.length) {
      return live.operatoryChairs;
    }
    const bundle = bundleFromSnapshot(snapshot);
    const op = bundle && bundle.softdent && bundle.softdent.operatory;
    if (op && Array.isArray(op.operatoryChairs) && op.operatoryChairs.length) {
      return op.operatoryChairs;
    }
    const sd = snapshot && snapshot.dashboards && snapshot.dashboards.softdent;
    if (sd && Array.isArray(sd.operatoryChairs) && sd.operatoryChairs.length) {
      return sd.operatoryChairs;
    }
    return null;
  }

  return {
    collectionsDaily,
    newPatientsMtd,
    appointmentsSnapshot,
    claimsOutstanding,
    providerProduction,
    adjustmentLog,
    patientRetention,
    operatoryGrid,
    prefetchLive,
    clearLiveCache,
    getLiveCache: () => liveCache,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = NR2SoftdentDaily;
}
if (typeof globalThis !== "undefined") {
  globalThis.NR2SoftdentDaily = NR2SoftdentDaily;
}
if (typeof window !== "undefined") {
  window.NR2SoftdentDaily = NR2SoftdentDaily;
}

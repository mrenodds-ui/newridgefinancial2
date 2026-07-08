/**
 * SoftDent daily widgets (browser) — mirrors nr2_softdent_daily.py via import bundle / NR2Analytics.
 */
const NR2SoftdentDaily = (function () {
  function parseMoney(value) {
    const n = Number(String(value || "0").replace(/[$,]/g, ""));
    return Number.isFinite(n) ? n : 0;
  }

  function analyticsApi() {
    return typeof NR2Analytics !== "undefined" ? NR2Analytics : null;
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
    const A = analyticsApi();
    if (!A) return { hasData: false, labels: [], values: [] };
    const bundle = bundleFromSnapshot(snapshot);
    const payments = [];
    const daysheet = A.softdentProductionDaily ? A.softdentProductionDaily(snapshot) : null;
    if (bundle && bundle.softdent && bundle.softdent.dashboard) {
      const rows = Array.isArray(bundle.softdent.dashboard) ? bundle.softdent.dashboard : bundle.softdent.dashboard.rows || [];
      return {
        hasData: rows.some((row) => Number(row.collections || row.Collections) > 0),
        labels: rows.map((row) => String(row.period || row.Period || "")).filter(Boolean),
        values: rows.map((row) => Number(row.collections || row.Collections || 0)),
        source: "dashboard-monthly",
      };
    }
    return { hasData: false, labels: [], values: [], source: payments.length ? "payments" : "none" };
  }

  function newPatientsMtd(snapshot) {
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
    return { hasData: false, adjustments: [] };
  }

  function patientRetention(snapshot) {
    const practice = snapshot && snapshot.dashboards && snapshot.dashboards.practice;
    const active = Number(practice && practice.patientCount) || 0;
    return { hasData: active > 0, activePatients: active, returningRatePct: null };
  }

  return {
    collectionsDaily,
    newPatientsMtd,
    appointmentsSnapshot,
    claimsOutstanding,
    providerProduction,
    adjustmentLog,
    patientRetention,
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

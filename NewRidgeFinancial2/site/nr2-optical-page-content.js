/* Documents / Library — inbox counts + SoftDent extract · no invent catalog */
(function () {
  const W = window.NR2OpticalWire;
  if (!W) return;

  async function boot() {
    W.setBanner("partial", "Wiring import inbox + SoftDent extract · empty ≠ $0");
    W.setText("val-inbox", null, "—");
    W.setText("val-odbc", null, "—");
    W.setText("val-census", null, "—");
    W.setText("val-codes", "UNAVAILABLE");

    const [inbox, odbc, retention] = await Promise.all([
      W.getJson("/api/import/inbox-summary", 12000),
      W.getJson("/api/softdent/odbc-status", 12000),
      W.getJson("/api/softdent/patient-retention", 12000),
    ]);

    let live = false;

    if (inbox.ok && inbox.data && inbox.data.hasData) {
      const sd = Number(inbox.data.softdentFiles || 0);
      const qb = Number(inbox.data.quickbooksFiles || 0);
      W.setText("val-inbox", "SD " + sd + " · QB " + qb);
      const hint = document.getElementById("hint-inbox");
      if (hint) {
        hint.textContent =
          "inbox files " +
          (inbox.data.totalFiles != null ? inbox.data.totalFiles : sd + qb) +
          " · counts only · empty ≠ $0";
      }
      live = true;
    } else if (inbox.ok && inbox.data && inbox.data.hasData === false) {
      W.setText("val-inbox", null, "∅");
    } else {
      W.setText("val-inbox", null, "NO SIGNAL");
    }

    if (odbc.ok && odbc.data && odbc.data.ok) {
      const when = odbc.data.lastExtractAt ? String(odbc.data.lastExtractAt).slice(0, 16).replace("T", " ") : "";
      W.setText("val-odbc", when || "EXTRACT OK");
      const hint = document.getElementById("hint-odbc");
      if (hint) {
        const mode = odbc.data.lastMode ? String(odbc.data.lastMode) : "";
        hint.textContent =
          "SoftDent extract" +
          (mode ? " · " + mode : "") +
          (odbc.data.odbcConfigured ? " · ODBC" : " · json-fallback") +
          " · read-only";
      }
      live = true;
    } else {
      W.setText("val-odbc", null, odbc.ok ? "∅" : "NO SIGNAL");
    }

    if (retention.ok && retention.data && retention.data.hasData) {
      const active = retention.data.activePatients != null ? Number(retention.data.activePatients) : null;
      const visits = retention.data.recentVisits != null ? Number(retention.data.recentVisits) : null;
      const bits = [];
      if (active != null) bits.push(active.toLocaleString("en-US") + " active");
      if (visits != null) bits.push(visits.toLocaleString("en-US") + " visits");
      if (bits.length) {
        W.setText("val-census", bits.join(" · "));
        const hint = document.getElementById("hint-census");
        if (hint) {
          hint.textContent =
            "retention window " +
            (retention.data.windowMonths != null ? retention.data.windowMonths + "mo" : "?") +
            (retention.data.returningRatePct != null
              ? " · return " + retention.data.returningRatePct + "%"
              : "") +
            " · counts only";
        }
        live = true;
      } else {
        W.setText("val-census", null, "∅");
      }
    } else {
      W.setText("val-census", null, retention.ok ? "∅" : "NO SIGNAL");
    }

    const ready = await W.getJson("/api/import-readiness", 12000);
    const readyData = ready.ok ? ready.data : null;
    const mode = W.bannerModeFromReady ? W.bannerModeFromReady(readyData, live) : live ? "live" : "partial";
    const red = W.lasersRed ? W.lasersRed(readyData) : false;
    W.setBanner(
      mode,
      red
        ? "Documents · inbox wired · lasers STALE · codes/payers UNAVAILABLE · empty ≠ $0"
        : live
          ? "Documents · inbox + extract LIVE · codes/payers UNAVAILABLE · empty ≠ $0"
          : "Documents · partial wire · codes/payers UNAVAILABLE · empty ≠ $0"
    );
  }

  boot().catch((err) => {
    W.setBanner("partial", "Documents wire fault · " + String(err && err.message ? err.message : err));
  });
})();

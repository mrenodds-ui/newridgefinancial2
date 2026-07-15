/* Narratives — probe APIs; stay UNAVAILABLE when packs gone (no fake DRAFT) */
(function () {
  const W = window.NR2OpticalWire;
  if (!W) return;

  async function boot() {
    W.setBanner("unavailable", "Narratives pack removed · empty ≠ $0 · no invent findings");
    const tpl = await W.getJson("/api/apex/narratives/payer-templates", 8000);
    const audit = await W.getJson("/api/apex/narratives/audit?limit=5", 8000);
    const ready = await W.getJson("/api/import-readiness", 8000);
    const readyData = ready.ok ? ready.data : null;
    const red = W.lasersRed ? W.lasersRed(readyData) : false;
    if (tpl.ok && tpl.data && tpl.data.ok && Array.isArray(tpl.data.templates)) {
      W.setText("val-tpl", String(tpl.data.templates.length) + " templates");
      W.setBanner(
        "partial",
        red
          ? "Templates present · lasers STALE · generate still gated · empty ≠ $0"
          : "Templates available · generate still gated · empty ≠ $0"
      );
    } else {
      W.setText("val-tpl", "UNAVAILABLE");
    }
    if (audit.ok && audit.data && audit.data.ok && Array.isArray(audit.data.entries)) {
      W.setText("val-audit", String(audit.data.entries.length) + " entries");
    } else {
      W.setText("val-audit", "UNAVAILABLE");
    }
    W.setText("val-gen", "UNAVAILABLE");
  }

  boot().catch((err) => {
    W.setBanner("unavailable", "Narratives probe fault · " + String(err && err.message ? err.message : err));
  });
})();

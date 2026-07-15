/* Office Manager — readiness + health only (no fake board actions) */
(function () {
  const W = window.NR2OpticalWire;
  if (!W) return;

  async function boot() {
    W.setBanner("partial", "OM readiness pulse · board-actions UNAVAILABLE · empty ≠ $0");
    const ready = await W.getJson("/api/import-readiness", 12000);
    const health = await W.getJson("/api/health", 8000);

    if (ready.ok && ready.data) {
      const blocking = Array.isArray(ready.data.blocking) ? ready.data.blocking.length : 0;
      const level = String(ready.data.level || "unknown").toUpperCase();
      W.setText("val-ready", level + (blocking ? " · block " + blocking : " · clear"));
      const hint = document.getElementById("hint-ready");
      if (hint) {
        hint.textContent =
          blocking > 0
            ? "Blocking critical gaps · lasers red on main"
            : "No blocking gaps · soft stale may still dim AR";
      }
      W.setBanner(
        blocking ? "partial" : "live",
        blocking
          ? "OM · import BLOCKED · fix SoftDent/QB before money ops"
          : "OM · import readiness clear · sync via main"
      );
    } else {
      W.setText("val-ready", "NO SIGNAL");
    }

    if (health.ok && health.data) {
      const bits = [];
      bits.push(health.data.db ? "DB" : "DB↓");
      bits.push(health.data.ollama ? "OLLAMA" : "OLLAMA↓");
      W.setText("val-health", bits.join(" · "));
    } else {
      W.setText("val-health", "NO SIGNAL");
    }
    W.setText("val-ov", "UNAVAILABLE");
  }

  boot().catch((err) => {
    W.setBanner("partial", "OM wire fault · " + String(err && err.message ? err.message : err));
  });
})();

/* Office Manager — readiness + SoftDent ops · no fake board actions */
(function () {
  const W = window.NR2OpticalWire;
  if (!W) return;

  function countApptSlots(data) {
    if (!data || !Array.isArray(data.operatories)) return null;
    let n = 0;
    data.operatories.forEach(function (op) {
      if (op && Array.isArray(op.slots)) n += op.slots.length;
    });
    return n;
  }

  function gapKeys(ready) {
    const keys = [];
    const seen = {};
    function add(list) {
      (list || []).forEach(function (g) {
        if (!g || typeof g !== "object") return;
        const k = String(g.datasetKey || g.key || "").trim();
        if (!k || seen[k]) return;
        seen[k] = true;
        keys.push(k);
      });
    }
    add(ready.blocking);
    const gaps = (ready.datasetGaps || []).concat(
      (ready.completeness && ready.completeness.softGaps) || []
    );
    add(
      gaps.filter(function (g) {
        return g && /stale|missing|partial/i.test(String(g.status || ""));
      })
    );
    return keys;
  }

  async function boot() {
    W.setBanner("partial", "OM wiring readiness + SoftDent day pulse · empty ≠ $0");
    W.setText("val-ready", null, "—");
    W.setText("val-ops", null, "—");
    W.setText("val-gaps", null, "—");
    W.setText("val-health", null, "—");

    const [ready, health, np, appt] = await Promise.all([
      W.getJson("/api/import-readiness", 12000),
      W.getJson("/api/health", 12000),
      W.getJson("/api/softdent/new-patients-mtd", 12000),
      W.getJson("/api/softdent/appointments-today", 12000),
    ]);

    let live = false;
    let blocked = false;

    if (ready.ok && ready.data) {
      const blocking = Array.isArray(ready.data.blocking) ? ready.data.blocking.length : 0;
      blocked = blocking > 0;
      const level = String(ready.data.level || "unknown").toUpperCase();
      const sum = ready.data.summary || {};
      W.setText(
        "val-ready",
        level + (blocking ? " · block " + blocking : " · clear") +
          (sum.stale != null ? " · stale " + sum.stale : "")
      );
      const keys = gapKeys(ready.data);
      if (keys.length) {
        W.setText("val-gaps", keys.slice(0, 3).join(" · ") + (keys.length > 3 ? " +" + (keys.length - 3) : ""));
        const gh = document.getElementById("hint-gaps");
        if (gh) gh.textContent = keys.length + " gap key(s) · lasers may red · empty ≠ $0";
      } else {
        W.setText("val-gaps", "NONE");
      }
      const hint = document.getElementById("hint-ready");
      if (hint) {
        hint.textContent = blocked
          ? "Blocking critical gaps · lasers red on main"
          : "No blocking · brief soft stale under TTL stays green lasers";
      }
      live = true;
    } else {
      W.setText("val-ready", "NO SIGNAL");
      W.setText("val-gaps", "NO SIGNAL");
    }

    const opsBits = [];
    if (np.ok && np.data && np.data.hasData && np.data.count != null) {
      opsBits.push(String(np.data.count) + " NP");
      const oh = document.getElementById("hint-ops");
      if (oh) {
        oh.textContent =
          "new patients" + (np.data.period ? " · " + np.data.period : "") + " · appointments today";
      }
      live = true;
    }
    if (appt.ok && appt.data && appt.data.hasData) {
      const slots = countApptSlots(appt.data);
      if (slots != null) {
        opsBits.push(String(slots) + " appts");
        live = true;
      }
    }
    if (opsBits.length) {
      W.setText("val-ops", opsBits.join(" · "));
    } else {
      W.setText("val-ops", null, np.ok || appt.ok ? "∅" : "NO SIGNAL");
    }

    if (health.ok && health.data) {
      const bits = [];
      bits.push(health.data.db ? "DB" : "DB↓");
      bits.push(health.data.ollama ? "OLLAMA" : "OLLAMA↓");
      if (health.data.readinessLevel) bits.push(String(health.data.readinessLevel).toUpperCase());
      W.setText("val-health", bits.join(" · "));
      live = true;
    } else {
      W.setText("val-health", "NO SIGNAL");
    }

    W.setBanner(
      blocked ? "partial" : live ? "live" : "partial",
      blocked
        ? "OM · import BLOCKED · re-export SoftDent Account Aging if softdent.ar stale · sync via main"
        : "OM · SoftDent day pulse + readiness · board-actions NAVIGATE live · empty ≠ $0"
    );
  }

  boot().catch((err) => {
    W.setBanner("partial", "OM wire fault · " + String(err && err.message ? err.message : err));
  });
})();

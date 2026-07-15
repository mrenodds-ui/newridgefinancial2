/* nr2-12017-optical-ops — live wire + P2 honesty (CSP script-src 'self') */
(function () {
  const toast = (msg) => {
    const el = document.getElementById("toast");
    if (!el) return;
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 2800);
  };

  let sessionToken = "";
  let role = "om";
  let syncBusy = false;
  let selectedPeriod = "60";

  function money(n) {
    if (n == null || !Number.isFinite(Number(n))) return null;
    return Number(n);
  }
  function fmtMoney(n) {
    const v = money(n);
    if (v == null) return null;
    return "$" + v.toLocaleString("en-US", { maximumFractionDigits: 0 });
  }
  function setMetric(id, value, opts) {
    const el = document.getElementById(id);
    if (!el) return;
    if (value == null || value === "") {
      el.textContent = opts && opts.emptyLabel ? opts.emptyLabel : "—";
      el.classList.add("empty");
      return;
    }
    el.textContent = value;
    el.classList.remove("empty");
  }
  function setWireMark(live, text) {
    const el = document.getElementById("wire-mark");
    if (!el) return;
    el.textContent = text;
    el.classList.toggle("live", !!live);
  }

  async function api(path, init) {
    const headers = Object.assign({ Accept: "application/json" }, (init && init.headers) || {});
    if (init && init.method && init.method.toUpperCase() !== "GET" && sessionToken) {
      headers["X-NR2-Session-Token"] = sessionToken;
      headers["Content-Type"] = headers["Content-Type"] || "application/json";
    }
    let res;
    try {
      res = await fetch(path, Object.assign({ cache: "no-store" }, init || {}, { headers }));
    } catch (err) {
      const aborted = err && (err.name === "AbortError" || err.code === 20);
      return {
        ok: false,
        status: aborted ? 408 : 0,
        data: { error: aborted ? "request_aborted" : String(err && err.message ? err.message : err) },
        aborted: !!aborted,
      };
    }
    let data = null;
    try {
      data = await res.json();
    } catch (_) {
      data = null;
    }
    return { ok: res.ok, status: res.status, data: data };
  }

  function tick() {
    const clock = document.getElementById("clock");
    if (clock) clock.textContent = new Date().toISOString().slice(11, 19) + " UTC";
  }
  tick();
  setInterval(tick, 1000);

  function applyRole() {
    const locked = role === "fd";
    document.querySelectorAll(".inst, .ctrl").forEach((n) => n.classList.toggle("locked", locked));
    document.querySelectorAll("[data-act], #wheel button").forEach((n) => {
      if (n.id === "scram") return;
      n.disabled = locked;
    });
    const om = document.getElementById("role-om");
    const fd = document.getElementById("role-fd");
    if (om) om.classList.toggle("on", role === "om");
    if (fd) fd.classList.toggle("on", role === "fd");
  }
  const roleOm = document.getElementById("role-om");
  const roleFd = document.getElementById("role-fd");
  if (roleOm) roleOm.onclick = () => {
    role = "om";
    applyRole();
    toast("RBAC: office_manager keys inserted");
  };
  if (roleFd) roleFd.onclick = () => {
    role = "fd";
    applyRole();
    toast("RBAC shutters closed — Front Desk view-only");
  };
  applyRole();

  const scram = document.getElementById("scram");
  if (scram) {
    scram.disabled = true;
    scram.onclick = (e) => {
      e.preventDefault();
      toast("SCRAM demoted: no emergency halt API — ornamental only");
    };
  }

  /* —— beams —— */
  function localPoint(bench, clientX, clientY) {
    const br = bench.getBoundingClientRect();
    return { x: clientX - br.left, y: clientY - br.top };
  }
  function rimPoint(center, from, r) {
    const dx = from.x - center.x;
    const dy = from.y - center.y;
    const len = Math.hypot(dx, dy) || 1;
    return { x: center.x + (dx / len) * r, y: center.y + (dy / len) * r };
  }
  function placeRay(id, a, b) {
    const el = document.getElementById(id);
    if (!el) return;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len = Math.hypot(dx, dy);
    const deg = (Math.atan2(dy, dx) * 180) / Math.PI;
    el.style.transformOrigin = "0 50%";
    el.style.width = Math.max(len, 0) + "px";
    el.style.left = a.x + "px";
    el.style.top = a.y - 2 + "px";
    el.style.transform = "rotate(" + deg + "deg)";
  }
  function snapBeams() {
    const bench = document.getElementById("bench");
    const core = document.getElementById("core");
    const sd = document.getElementById("emitter-sd");
    const qb = document.getElementById("emitter-qb");
    const tax = document.getElementById("tax");
    const ctrl = document.getElementById("ctrl");
    if (!bench || !core || !sd || !qb || !tax || !ctrl) return;
    const cr = core.getBoundingClientRect();
    if (cr.width < 4) return;
    const center = localPoint(bench, cr.left + cr.width / 2, cr.top + cr.height / 2);
    const radius = cr.width / 2;
    const sr = sd.getBoundingClientRect();
    const sdStart = localPoint(bench, sr.right + 6, sr.top + sr.height * 0.42);
    const qr = qb.getBoundingClientRect();
    const qbStart = localPoint(bench, qr.left - 6, qr.top + qr.height * 0.42);
    const tr = tax.getBoundingClientRect();
    const taxStart = localPoint(bench, tr.left - 6, tr.top + tr.height * 0.5);
    const ctr = ctrl.getBoundingClientRect();
    const ctrlStart = localPoint(bench, ctr.right + 6, ctr.top + ctr.height * 0.5);
    placeRay("ray-sd", sdStart, rimPoint(center, sdStart, radius));
    placeRay("ray-qb", qbStart, rimPoint(center, qbStart, radius));
    placeRay("ray-tax", taxStart, rimPoint(center, taxStart, radius));
    placeRay("ray-ctrl", ctrlStart, rimPoint(center, ctrlStart, radius));
  }
  window.snapBeams = snapBeams;
  snapBeams();
  requestAnimationFrame(function () {
    requestAnimationFrame(snapBeams);
  });
  setTimeout(snapBeams, 50);
  setTimeout(snapBeams, 250);
  window.addEventListener("resize", snapBeams);
  if (typeof ResizeObserver !== "undefined") {
    const bench = document.getElementById("bench");
    if (bench) new ResizeObserver(snapBeams).observe(bench);
  }

  /* —— live wires —— */
  async function ensureSession() {
    const r = await api("/api/browser-session");
    if (r.data && r.data.sessionToken) {
      sessionToken = String(r.data.sessionToken);
      return true;
    }
    return false;
  }

  async function refreshLasers() {
    const align = document.getElementById("align");
    const r = await api("/api/import-readiness");
    if (!r.ok || !r.data) {
      if (align) {
        align.classList.add("bad");
        align.title = "Import readiness unavailable";
      }
      return null;
    }
    const ready = r.data;
    const blocking = Array.isArray(ready.blocking) ? ready.blocking : [];
    const gaps = Array.isArray(ready.datasetGaps) ? ready.datasetGaps : [];
    const softGaps =
      ready.completeness && Array.isArray(ready.completeness.softGaps)
        ? ready.completeness.softGaps
        : [];
    const criticalSoft = gaps
      .concat(softGaps)
      .filter((g) => g && String(g.severity || "") === "critical");
    const staleCritical = criticalSoft.filter((g) =>
      /stale|missing/i.test(String(g.status || ""))
    );
    const ok =
      ready.ok !== false && blocking.length === 0 && staleCritical.length === 0;
    if (align) {
      align.classList.toggle("bad", !ok);
      align.title = ok
        ? "Import readiness coherent · lasers green-path"
        : "Import gaps / stale · lasers red (blocking=" +
          blocking.length +
          ", criticalSoft=" +
          staleCritical.length +
          ")";
    }
    const state = document.getElementById("hal-state");
    if (state) {
      state.textContent = ok ? "RECON · STANDBY" : "RECON · INCOHERENT";
      state.style.color = ok ? "" : "var(--fringe)";
    }
    return ready;
  }

  async function refreshMetrics() {
    const sdStatus = document.getElementById("sd-status");
    const qbStatus = document.getElementById("qb-status");
    const sdSub = document.getElementById("sd-sub");

    const claims = await api("/api/softdent/claims-outstanding?limit=25");
    if (claims.ok && claims.data && claims.data.hasData) {
      const list = Array.isArray(claims.data.claims) ? claims.data.claims : [];
      const count = claims.data.count != null ? Number(claims.data.count) : list.length;
      const total = money(claims.data.totalOutstanding);
      const shown = total != null ? fmtMoney(total) : null;
      if (shown) {
        setMetric("metric-sd", shown);
        if (sdStatus) sdStatus.textContent = "CLAIMS · LIVE";
        if (sdSub) {
          sdSub.textContent =
            "claims outstanding" +
            (count ? " · " + count + " open" : "") +
            " · empty ≠ $0 · no write-back";
        }
      } else {
        setMetric("metric-sd", null);
        if (sdStatus) sdStatus.textContent = "∅ EMPTY";
      }
      await refreshFilm(claims.data);
    } else {
      setMetric("metric-sd", null, { emptyLabel: "∅" });
      if (sdStatus) sdStatus.textContent = "NO SIGNAL";
      if (sdSub) sdSub.textContent = "no claims signal · empty ≠ $0 · no SoftDent write-back";
      await refreshFilm(null);
    }

    const qb = await api("/api/qb/monthly-revenue");
    if (qb.ok && qb.data && qb.data.hasData && Array.isArray(qb.data.values) && qb.data.values.length) {
      const last = qb.data.values[qb.data.values.length - 1];
      const shown = fmtMoney(last);
      if (shown) {
        setMetric("metric-qb", shown);
        if (qbStatus) qbStatus.textContent = "LIVE";
        const lbl = Array.isArray(qb.data.labels) ? qb.data.labels[qb.data.labels.length - 1] : "";
        const qbSub = document.getElementById("qb-sub");
        if (qbSub) qbSub.textContent = "monthly revenue" + (lbl ? " · " + lbl : "") + " · empty ≠ $0";
      } else {
        setMetric("metric-qb", null, { emptyLabel: "∅" });
        if (qbStatus) qbStatus.textContent = "∅ EMPTY";
      }
    } else {
      setMetric("metric-qb", null, { emptyLabel: "∅" });
      if (qbStatus) qbStatus.textContent = "NO SIGNAL";
    }
  }

  async function refreshFilm(claimsData) {
    const slots = document.querySelectorAll("#film .slot");
    if (!slots.length) return;
    const list =
      claimsData && claimsData.hasData && Array.isArray(claimsData.claims)
        ? claimsData.claims.slice(0, slots.length)
        : [];
    slots.forEach((slot, i) => {
      const c = list[i];
      if (!c) {
        slot.classList.add("empty");
        slot.innerHTML = "∅";
        slot.title = "No claim stub · empty ≠ $0";
        return;
      }
      slot.classList.remove("empty");
      const amt = money(c.amount);
      const label =
        String(c.claimId || c.patientName || "claim").slice(0, 14) +
        (amt != null ? " · $" + Math.round(amt) : "");
      slot.innerHTML = '<div class="mini"></div>' + label.replace(/</g, "");
      slot.title =
        String(c.payer || "") +
        " · " +
        String(c.serviceDate || "") +
        " · " +
        String(c.status || "") +
        " · read-only";
    });
  }

  async function bootWire() {
    setWireMark(false, "CONNECTING · SESSION + READINESS");
    try {
      const okSession = await ensureSession();
      const ready = await refreshLasers();
      await refreshMetrics();
      if (okSession && ready) {
        setWireMark(true, "LIVE SIGNAL · empty ≠ $0 · no SoftDent write-back");
        toast("Optical wires live · lasers + SoftDent claims + QB revenue");
      } else if (ready) {
        setWireMark(false, "READINESS OK · SESSION WEAK — mutations may 403");
      } else {
        setWireMark(false, "PARTIAL WIRE · CHECK IMPORT-READINESS");
      }
    } catch (err) {
      setWireMark(false, "WIRE FAILED · " + String(err && err.message ? err.message : err));
    }
  }

  const wheel = document.getElementById("wheel");
  if (wheel) {
    wheel.onclick = async (e) => {
      const b = e.target.closest("button[data-period]");
      if (!b || role === "fd") return;
      document.querySelectorAll("#wheel button").forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
      selectedPeriod = b.dataset.period || selectedPeriod;
      toast("Period " + selectedPeriod + "d selected · pressing REFRESH-PERIOD posts SoftDent refresh");
    };
  }

  async function doSync(btn) {
    if (syncBusy) return;
    syncBusy = true;
    if (btn) btn.classList.add("busy");
    const led = document.getElementById("pulse-led");
    if (led) {
      led.classList.remove("idle");
      led.classList.add("on");
    }
    toast("SYNC → POST /api/apex/sync/trigger …");
    const r = await api("/api/apex/sync/trigger", {
      method: "POST",
      body: JSON.stringify({ page: "financial", fullSync: true, actor: "optical-bench" }),
    });
    syncBusy = false;
    if (btn) btn.classList.remove("busy");
    if (led) {
      led.classList.remove("on");
      led.classList.add("idle");
    }
    if (r.status === 423) {
      toast("Sync locked — already in progress (423)");
      return;
    }
    if (!r.ok) {
      toast("Sync failed · " + (r.data && (r.data.error || r.data.status) || r.status));
      return;
    }
    toast("Sync ok · refreshing lasers + metrics");
    await refreshLasers();
    await refreshMetrics();
  }

  async function doRefreshPeriod() {
    toast("Period Wheel → POST /api/apex/softdent/refresh-period · " + selectedPeriod + "d …");
    const ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timer = ctrl ? setTimeout(() => ctrl.abort(), 15000) : null;
    const r = await api("/api/apex/softdent/refresh-period", {
      method: "POST",
      body: JSON.stringify({ periodDays: Number(selectedPeriod) || 60 }),
      signal: ctrl ? ctrl.signal : undefined,
    });
    if (timer) clearTimeout(timer);
    if (r.aborted || r.status === 408 || r.status === 504) {
      toast("Refresh stalled — check SoftDent ODBC / sign-on (timeout)");
      return;
    }
    if (!r.ok) {
      toast("Refresh-period failed · " + (r.data && r.data.error || r.status));
      return;
    }
    toast(r.data && r.data.ok ? "SoftDent period refresh ok" : "Refresh returned · check SoftDent sign-on");
    await refreshLasers();
    await refreshMetrics();
  }

  async function doRecon() {
    const state = document.getElementById("hal-state");
    if (state) state.textContent = "RECON · RUNNING";
    toast("HAL → POST /api/apex/hal/reconciliation …");
    const r = await api("/api/apex/hal/reconciliation", {
      method: "POST",
      body: JSON.stringify({ classifyOnly: false, explain: false }),
    });
    if (!r.ok || (r.data && r.data.available === false)) {
      if (state) state.textContent = "RECON · UNAVAILABLE";
      toast(
        "Reconciliation UNAVAILABLE · " +
          ((r.data && (r.data.reason || r.data.error)) || r.status) +
          " · clean-slate (no pack)"
      );
      return;
    }
    const ok = !!(r.data && r.data.ok);
    if (state) state.textContent = ok ? "RECON · COHERENT" : "RECON · INCOHERENT";
    toast(ok ? "Reconciliation ok" : "Reconciliation completed with gaps");
  }

  async function doTax() {
    toast("Tax Prism → POST /api/apex/tax/calculate-planning …");
    const r = await api("/api/apex/tax/calculate-planning", {
      method: "POST",
      body: JSON.stringify({}),
    });
    const metric = document.getElementById("metric-tax");
    if (!r.ok) {
      toast("Tax planning failed · " + (r.data && r.data.error || r.status));
      if (metric) metric.textContent = "ERR";
      return;
    }
    const plan = r.data || {};
    const label =
      plan.effective_rate != null
        ? (Number(plan.effective_rate) * 100).toFixed(1) + "% EFF"
        : plan.taxable_income != null
          ? fmtMoney(plan.taxable_income) || "PLAN"
          : "PLAN OK";
    if (metric) {
      metric.textContent = label;
      metric.classList.remove("empty");
    }
    toast((plan.disclaimer || "PLANNING ONLY — CPA REVIEW") + "");
  }

  const benchEl = document.getElementById("bench");
  if (benchEl) {
    benchEl.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-act]");
      if (!btn) return;
      if (role === "fd") {
        toast("Shutter locked — Front Desk cannot mutate");
        return;
      }
      const act = btn.dataset.act;
      if (act === "sync") return void doSync(btn);
      if (act === "refresh") return void doRefreshPeriod();
      if (act === "recon") return void doRecon();
      if (act === "tax") return void doTax();
    });
  }

  bootWire();
  setInterval(refreshLasers, 60000);
})();

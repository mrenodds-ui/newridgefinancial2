/* nr2-12014-lower-ctrl-beam — external (CSP script-src 'self') */
(function () {
  const toast = (msg) => {
    const el = document.getElementById("toast");
    if (!el) return;
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 2400);
  };

  function tick() {
    const clock = document.getElementById("clock");
    if (clock) clock.textContent = new Date().toISOString().slice(11, 19) + " UTC";
  }
  tick();
  setInterval(tick, 1000);

  let role = "om";
  function applyRole() {
    const locked = role === "fd";
    document.querySelectorAll(".inst, .ctrl").forEach((n) => n.classList.toggle("locked", locked));
    const om = document.getElementById("role-om");
    const fd = document.getElementById("role-fd");
    if (om) om.classList.toggle("on", role === "om");
    if (fd) fd.classList.toggle("on", role === "fd");
    toast(locked ? "RBAC shutters closed — capabilities required" : "RBAC: office_manager keys inserted");
  }
  const roleOm = document.getElementById("role-om");
  const roleFd = document.getElementById("role-fd");
  if (roleOm) roleOm.onclick = () => { role = "om"; applyRole(); };
  if (roleFd) roleFd.onclick = () => { role = "fd"; applyRole(); };
  applyRole();

  const scram = document.getElementById("scram");
  if (scram) scram.onclick = () => location.reload();

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

  const wheel = document.getElementById("wheel");
  if (wheel) {
    wheel.onclick = (e) => {
      const b = e.target.closest("button[data-period]");
      if (!b || role === "fd") return;
      document.querySelectorAll("#wheel button").forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
      toast("Period Wheel → POST softdent/refresh-period · " + b.dataset.period + "d (mock bind)");
    };
  }

  let syncBusy = false;
  const benchEl = document.getElementById("bench");
  if (benchEl) {
    benchEl.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-act]");
      if (!btn) return;
      if (role === "fd") {
        toast("Shutter locked — insufficient capability");
        return;
      }
      const act = btn.dataset.act;
      if (act === "sync") {
        if (syncBusy) return;
        syncBusy = true;
        btn.classList.add("busy");
        const led = document.getElementById("pulse-led");
        if (led) {
          led.classList.remove("idle");
          led.classList.add("on");
        }
        toast("HAL Core · SoftDent+QB sync → POST /api/apex/sync/trigger");
        setTimeout(() => {
          syncBusy = false;
          btn.classList.remove("busy");
          if (led) {
            led.classList.remove("on");
            led.classList.add("idle");
          }
          toast("Sync complete (mock) · SoftDent AR still stale / blocking HAL recon");
        }, 1600);
        return;
      }
      const map = {
        refresh: "SoftDent · Period Wheel → POST softdent/refresh-period → HAL context",
        recon: "HAL Core · POST hal/reconciliation (SoftDent+QB+Tax beams)",
        tax: "Tax Prism emitter · POST tax/calculate-planning · rolling beam → HAL",
      };
      toast(map[act] || act);
    });
  }
})();

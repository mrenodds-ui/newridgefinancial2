/* HAL chat — live wire POST /api/hal/evaluate-query + money honesty (CSP script-src 'self') */
(function () {
  const stream = document.getElementById("stream");
  const form = document.getElementById("compose");
  const input = document.getElementById("input");
  if (!stream || !form || !input) return;

  let sessionToken = "";
  let busy = false;

  function addMsg(role, text) {
    const el = document.createElement("div");
    el.className = "msg " + role;
    el.innerHTML =
      '<span class="who">' +
      (role === "hal" ? "HAL" : "OPERATOR") +
      "</span>" +
      String(text).replace(/</g, "&lt;");
    stream.appendChild(el);
    stream.scrollTop = stream.scrollHeight;
  }

  function looksMoney(q) {
    return /\$|claim|claims|revenue|outstanding|aging|\bar\b|dollar|total/i.test(q || "");
  }

  async function ensureSession() {
    try {
      const res = await fetch("/api/browser-session", { cache: "no-store" });
      const data = await res.json();
      if (data && data.sessionToken) {
        sessionToken = String(data.sessionToken);
        return true;
      }
    } catch (_) {}
    return false;
  }

  async function prefetchClaimsHint() {
    try {
      const res = await fetch("/api/softdent/claims-outstanding", { cache: "no-store" });
      const data = await res.json();
      if (!res.ok || !data) return "";
      if (!data.hasData) return " [beam: SoftDent claims ∅ · empty≠$0]";
      const total = data.totalOutstanding;
      if (total == null || !Number.isFinite(Number(total))) return " [beam: SoftDent claims LIVE]";
      return " [beam: SoftDent claims live $" + Number(total).toLocaleString("en-US", { maximumFractionDigits: 0 }) + "]";
    } catch (_) {
      return " [beam: SoftDent claims NO SIGNAL]";
    }
  }

  ensureSession().then((ok) => {
    const chip = document.querySelector(".hal-chip");
    if (chip) {
      chip.insertAdjacentHTML(
        "beforeend",
        ok
          ? ' <span style="color:var(--sd);margin-left:8px">STANDBY · LIVE GATE</span>'
          : ' <span style="color:var(--lock);margin-left:8px">SESSION WEAK</span>'
      );
    }
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = (input.value || "").trim();
    if (!q || busy) return;
    addMsg("user", q);
    input.value = "";
    busy = true;
    if (!sessionToken) await ensureSession();
    let queryOut = q;
    if (looksMoney(q)) {
      const hint = await prefetchClaimsHint();
      if (hint) queryOut = q + hint;
    }
    try {
      const res = await fetch("/api/hal/evaluate-query", {
        method: "POST",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          ...(sessionToken ? { "X-NR2-Session-Token": sessionToken } : {}),
        },
        body: JSON.stringify({ query: queryOut, stream: false }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        addMsg(
          "hal",
          "Transmit blocked · " +
            (data.error || data.detail || res.status) +
            ". Money answers gated by import-readiness; empty ≠ $0."
        );
      } else {
        const reply =
          data.reply ||
          data.response ||
          data.text ||
          (data.message && (data.message.content || data.message)) ||
          (data.result && (data.result.reply || data.result.text)) ||
          JSON.stringify(data).slice(0, 800);
        addMsg("hal", String(reply));
      }
    } catch (err) {
      addMsg("hal", "Link fault · " + String(err && err.message ? err.message : err));
    }
    busy = false;
  });
})();

/* HAL chat page — external for CSP script-src 'self' */
(function () {
  const stream = document.getElementById("stream");
  const form = document.getElementById("compose");
  const input = document.getElementById("input");
  if (!stream || !form || !input) return;

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

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = (input.value || "").trim();
    if (!q) return;
    addMsg("user", q);
    input.value = "";
    addMsg(
      "hal",
      "Mock spectral ack → would POST /api/hal/evaluate-query. " +
        "Live wiring uses local model only (cloud denied). Money answers gated by import-readiness; empty ≠ $0."
    );
  });
})();

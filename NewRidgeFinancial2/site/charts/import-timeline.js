/** Import health timeline — Moonshot Sprint 4 (Canvas Gantt). */
function renderImportTimeline(canvasId, sources) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !canvas.getContext) return;
  const ctx = canvas.getContext("2d");
  const rows = Array.isArray(sources) ? sources : [];
  const now = Date.now();
  const maxAgeMs = 48 * 3600 * 1000;
  const w = canvas.width || 360;
  const h = canvas.height || 160;
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = "rgba(255,255,255,0.06)";
  rows.forEach((_s, i) => {
    const y = i * 32 + 28;
    ctx.beginPath();
    ctx.moveTo(100, y);
    ctx.lineTo(w - 8, y);
    ctx.stroke();
  });
  rows.forEach((s, i) => {
    const age = s.lastSyncAt ? now - new Date(s.lastSyncAt).getTime() : maxAgeMs;
    const pct = Math.min(Math.max(age / maxAgeMs, 0), 1);
    const level = String(s.level || "unknown");
    ctx.fillStyle = level === "fresh" ? "#22c55e" : level === "stale" ? "#eab308" : "#ef4444";
    ctx.fillRect(100, i * 32 + 10, pct * (w - 120), 18);
    ctx.fillStyle = "#cbd5e1";
    ctx.fillText(String(s.name || s.id || "source"), 8, i * 32 + 24);
  });
}

if (typeof window !== "undefined") window.NR2Charts = window.NR2Charts || {};
if (typeof window !== "undefined") window.NR2Charts.renderImportTimeline = renderImportTimeline;

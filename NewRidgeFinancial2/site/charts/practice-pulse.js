/**
 * Practice Pulse + A/R waterfall mini charts — Moonshot holistic dashboard.
 */
function renderPracticePulse(canvasId, metrics) {
  const canvas = typeof canvasId === "string" ? document.getElementById(canvasId) : canvasId;
  if (!canvas || !canvas.getContext) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width || 360;
  const h = canvas.height || 140;
  ctx.clearRect(0, 0, w, h);
  const m = metrics || {};
  const production = Number(m.productionUsd || m.production || 0);
  const collections = Number(m.collectionsUsd || m.collections || 0);
  const arTotal = Number(m.arTotalUsd || m.arTotal || 0);
  const maxVal = Math.max(production, collections, arTotal, 1);
  const bars = [
    { label: "Prod", val: production, color: "#3b82f6" },
    { label: "Coll", val: collections, color: "#10b981" },
    { label: "A/R", val: arTotal, color: "#f59e0b" },
  ];
  const pad = 24;
  const barW = (w - pad * 2) / bars.length - 12;
  ctx.font = "11px system-ui,sans-serif";
  ctx.fillStyle = "#64748b";
  ctx.fillText("Practice Pulse", pad, 16);
  bars.forEach((b, i) => {
    const x = pad + i * (barW + 12);
    const bh = ((h - 50) * b.val) / maxVal;
    const y = h - 28 - bh;
    ctx.fillStyle = b.color;
    ctx.fillRect(x, y, barW, bh);
    ctx.fillStyle = "#334155";
    ctx.fillText(b.label, x, h - 10);
    ctx.fillText("$" + Math.round(b.val).toLocaleString(), x, y - 4);
  });
}

function renderArWaterfall(canvasId, buckets) {
  const canvas = typeof canvasId === "string" ? document.getElementById(canvasId) : canvasId;
  if (!canvas || !canvas.getContext) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width || 360;
  const h = canvas.height || 120;
  ctx.clearRect(0, 0, w, h);
  const rows = Array.isArray(buckets) ? buckets : [];
  const amounts = rows.map((r) => Number(r.amount || 0));
  const total = amounts.reduce((a, b) => a + b, 0) || 1;
  const colors = ["#22c55e", "#eab308", "#f97316", "#ef4444"];
  let x = 8;
  ctx.font = "10px system-ui,sans-serif";
  ctx.fillStyle = "#64748b";
  ctx.fillText("A/R Waterfall", 8, 14);
  rows.forEach((row, i) => {
    const amt = Number(row.amount || 0);
    const segW = ((w - 16) * amt) / total;
    ctx.fillStyle = colors[i % colors.length];
    ctx.fillRect(x, 28, Math.max(segW, 2), h - 44);
    if (segW > 36) {
      ctx.fillStyle = "#fff";
      ctx.fillText(String(row.bucket || ""), x + 4, 48);
    }
    x += segW;
  });
}

if (typeof window !== "undefined") {
  window.NR2Charts = window.NR2Charts || {};
  window.NR2Charts.renderPracticePulse = renderPracticePulse;
  window.NR2Charts.renderArWaterfall = renderArWaterfall;
}

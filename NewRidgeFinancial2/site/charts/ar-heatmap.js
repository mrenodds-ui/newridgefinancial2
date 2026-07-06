/** A/R aging heatmap — Moonshot Sprint 4 (Canvas). */
function renderARHeatmap(canvasId, buckets) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !canvas.getContext) return;
  const ctx = canvas.getContext("2d");
  const data = Array.isArray(buckets) ? buckets : [];
  const labels = ["0-30", "31-60", "61-90", "90+"];
  const w = canvas.width || 320;
  const h = canvas.height || 120;
  ctx.clearRect(0, 0, w, h);
  data.forEach((row, i) => {
    const amount = Number(row.amount || row.total || 0);
    const max = Math.max(...data.map((r) => Number(r.amount || r.total || 0)), 1);
    const barW = (amount / max) * (w - 80);
    ctx.fillStyle = ["#22c55e", "#eab308", "#f97316", "#ef4444"][i] || "#94a3b8";
    ctx.fillRect(70, i * 28 + 8, barW, 20);
    ctx.fillStyle = "#e2e8f0";
    ctx.fillText(labels[i] || row.bucket || "", 4, i * 28 + 22);
    ctx.fillText("$" + amount.toLocaleString(), w - 64, i * 28 + 22);
  });
}

if (typeof window !== "undefined") window.NR2Charts = window.NR2Charts || {};
if (typeof window !== "undefined") window.NR2Charts.renderARHeatmap = renderARHeatmap;

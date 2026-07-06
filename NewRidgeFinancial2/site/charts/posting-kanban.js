/** Posting queue Kanban columns — Moonshot Sprint 4. */
function renderPostingKanban(containerId, columns) {
  const root = document.getElementById(containerId);
  if (!root) return;
  root.innerHTML = "";
  const cols = columns || {
    pendingOcr: [],
    ready: [],
    exceptions: [],
    postedToday: [],
  };
  Object.entries(cols).forEach(([key, items]) => {
    const col = document.createElement("div");
    col.className = "nr2-kanban-col";
    const title = document.createElement("h4");
    title.textContent = key.replace(/([A-Z])/g, " $1");
    col.appendChild(title);
    (items || []).forEach((item) => {
      const card = document.createElement("div");
      card.className = "nr2-kanban-card";
      card.textContent = (item.description || item.id || "entry") + (item.amount ? " · " + item.amount : "");
      col.appendChild(card);
    });
    root.appendChild(col);
  });
}

if (typeof window !== "undefined") window.NR2Charts = window.NR2Charts || {};
if (typeof window !== "undefined") window.NR2Charts.renderPostingKanban = renderPostingKanban;

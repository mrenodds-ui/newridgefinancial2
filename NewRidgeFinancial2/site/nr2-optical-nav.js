(() => {
  const pages = [
    { href: "/nr2-optical-beam-touch-mockup.html", label: "MAIN · LANDING" },
    { href: "/nr2-optical-pages-hub.html", label: "PAGES HUB" },
    { group: "SOURCES" },
    { href: "/nr2-optical-page-softdent.html", label: "SoftDent" },
    { href: "/nr2-optical-page-quickbooks.html", label: "QuickBooks" },
    { href: "/nr2-optical-page-ar.html", label: "A/R Aging" },
    { group: "HAL" },
    { href: "/nr2-optical-page-hal.html", label: "HAL + Chat" },
    { href: "/nr2-optical-page-claims.html", label: "Claims + ERA" },
    { href: "/nr2-optical-page-narratives.html", label: "Narratives" },
    { group: "PLANNING" },
    { href: "/nr2-optical-page-taxes.html", label: "Taxes" },
    { href: "/nr2-optical-page-office-manager.html", label: "Office Manager" },
    { href: "/nr2-optical-page-content.html", label: "Documents / Library" },
  ];
  const nav = document.getElementById("nav");
  if (!nav) return;
  const here = location.pathname.split("/").pop() || "";
  let html = `<div class="brand">NR2 · OPTICAL</div>`;
  for (const p of pages) {
    if (p.group) {
      html += `<div class="group">${p.group}</div>`;
      continue;
    }
    const on = here && p.href.endsWith(here) ? " on" : "";
    html += `<a class="${on.trim()}" href="${p.href}">${p.label}</a>`;
  }
  nav.innerHTML = html;
})();

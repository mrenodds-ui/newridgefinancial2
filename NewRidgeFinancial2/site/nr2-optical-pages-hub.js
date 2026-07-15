/* Pages Hub — LIVE/STALE from import-readiness lasers · stamp from /api/app-info */
(function () {
  const W = window.NR2OpticalWire;
  if (!W) return;

  const CARD_MATCHERS = [
    { id: "hub-main", prefixes: ["softdent.", "quickbooks."] },
    { id: "hub-softdent", prefixes: ["softdent."] },
    { id: "hub-quickbooks", prefixes: ["quickbooks."] },
    { id: "hub-hal", prefixes: ["softdent.", "quickbooks."] },
    { id: "hub-claims", prefixes: ["softdent.claims"] },
    { id: "hub-taxes", prefixes: ["taxes.", "tax."] },
    { id: "hub-ar", prefixes: ["softdent.ar"] },
    { id: "hub-om", prefixes: ["softdent.", "quickbooks."] },
    { id: "hub-docs", prefixes: ["documents.", "softdent."] },
  ];

  function keysHit(keys, prefixes) {
    return (keys || []).some(function (k) {
      const key = String(k || "");
      return prefixes.some(function (p) {
        return key === p || key.indexOf(p) === 0;
      });
    });
  }

  function setVal(id, label, cls) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = label;
    el.classList.remove("empty", "bad", "stale", "sd", "qb", "hal");
    if (cls) el.classList.add(cls);
  }

  async function boot() {
    const [info, ready] = await Promise.all([
      W.getJson("/api/app-info", 8000),
      W.getJson("/api/import-readiness", 12000),
    ]);

    const stamp =
      (info.ok && info.data && (info.data.buildId || info.data.BUILD_ID || info.data.assetVersion)) ||
      "nr2-optical";
    const lasers =
      ready.ok && ready.data && ready.data.alignmentLasers
        ? ready.data.alignmentLasers
        : {};
    const blocking =
      ready.ok && ready.data && Array.isArray(ready.data.blocking) ? ready.data.blocking : [];
    const datasetKeys = Array.isArray(lasers.datasetKeys)
      ? lasers.datasetKeys
      : blocking
          .map(function (b) {
            return b && b.datasetKey;
          })
          .filter(Boolean);
    const red = lasers.red === true || blocking.length > 0;
    const level =
      ready.ok && ready.data ? String(ready.data.level || "unknown").toUpperCase() : "NO SIGNAL";

    W.setBanner(
      red ? "partial" : ready.ok ? "live" : "unavailable",
      (red ? "Lasers RED · " : "Lasers green-path · ") +
        "blocking " +
        blocking.length +
        " · " +
        level +
        " · stamp " +
        stamp
    );

    const title = document.querySelector("title");
    if (title) title.textContent = "NR2 Optical Pages Hub — " + stamp;

    CARD_MATCHERS.forEach(function (card) {
      const hit = keysHit(datasetKeys, card.prefixes);
      if (!ready.ok) {
        setVal(card.id, "NO SIGNAL", "stale");
        return;
      }
      if (hit || (red && (card.id === "hub-main" || card.id === "hub-hal" || card.id === "hub-om"))) {
        setVal(card.id, "STALE", "stale");
        return;
      }
      const tone =
        card.id.indexOf("qb") >= 0 || card.id === "hub-quickbooks" || card.id === "hub-taxes"
          ? "qb"
          : card.id === "hub-hal" || card.id === "hub-main"
            ? "hal"
            : "sd";
      setVal(card.id, "LIVE", tone);
    });

    setVal("hub-narratives", "UNAVAILABLE", "stale");
  }

  boot();
})();

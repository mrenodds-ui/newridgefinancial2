/* Optical board navigate — board-actions → consent → optical href (empty ≠ $0) */
(function (global) {
  const HREFS = {
    main: "/nr2-optical-beam-touch-mockup.html",
    landing: "/nr2-optical-beam-touch-mockup.html",
    financial: "/nr2-optical-beam-touch-mockup.html",
    hub: "/nr2-optical-pages-hub.html",
    pages: "/nr2-optical-pages-hub.html",
    softdent: "/nr2-optical-page-softdent.html",
    quickbooks: "/nr2-optical-page-quickbooks.html",
    qb: "/nr2-optical-page-quickbooks.html",
    ar: "/nr2-optical-page-ar.html",
    aging: "/nr2-optical-page-ar.html",
    claims: "/nr2-optical-page-claims.html",
    era: "/nr2-optical-page-claims.html",
    hal: "/nr2-optical-page-hal.html",
    taxes: "/nr2-optical-page-taxes.html",
    tax: "/nr2-optical-page-taxes.html",
    "office-manager": "/nr2-optical-page-office-manager.html",
    om: "/nr2-optical-page-office-manager.html",
    narratives: "/nr2-optical-page-narratives.html",
    content: "/nr2-optical-page-content.html",
    documents: "/nr2-optical-page-content.html",
    library: "/nr2-optical-page-content.html",
  };

  function normalizePageKey(page) {
    return String(page || "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9\-]/g, "");
  }

  function hrefForPage(pageOrHref) {
    const raw = String(pageOrHref || "").trim();
    if (!raw) return "";
    if (raw.indexOf("/nr2-optical") === 0) return raw.split("?")[0];
    const key = normalizePageKey(raw);
    return HREFS[key] || "";
  }

  function firstNavigate(actions) {
    const list = Array.isArray(actions) ? actions : [];
    for (let i = 0; i < list.length; i++) {
      const a = list[i];
      if (!a || a.type !== "navigate") continue;
      const href = a.href || hrefForPage(a.page || a.target);
      if (href) return { page: a.page || a.target || "", href: href };
    }
    return null;
  }

  function looksLikeNavAsk(query) {
    return /\b(go to|take me to|navigate|switch to|open (the )?(softdent|soft dent|quickbooks|qb|ar|a\/?r|claims|taxes?|office manager|om|narratives|documents|hub|main|landing)|show (me )?(the )?(softdent|quickbooks|qb|ar|claims|taxes?|office manager) (page|bench))\b/i.test(
      String(query || "")
    );
  }

  function navOnlyAsk(query) {
    const q = String(query || "").trim();
    return /^(go to|take me to|navigate( to)?|switch to|open)\b/i.test(q) && q.split(/\s+/).length <= 8;
  }

  global.NR2OpticalBoardNav = {
    HREFS: HREFS,
    hrefForPage: hrefForPage,
    firstNavigate: firstNavigate,
    looksLikeNavAsk: looksLikeNavAsk,
    navOnlyAsk: navOnlyAsk,
  };
})(typeof window !== "undefined" ? window : globalThis);

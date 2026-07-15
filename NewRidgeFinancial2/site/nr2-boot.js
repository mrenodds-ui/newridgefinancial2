/* CSP-safe boot — unregister legacy SW/caches; redirect only from entry shells. */
(function () {
  window.NR2_CLEAN_SLATE = true;
  const path = location.pathname || "";
  const isEntry = path === "/" || /\/index\.html$/i.test(path);
  (async function nr2CremateLegacy() {
    try {
      if (navigator.serviceWorker) {
        const regs = await navigator.serviceWorker.getRegistrations();
        await Promise.all(regs.map((r) => r.unregister()));
      }
    } catch (_) {}
    try {
      if (window.caches) {
        const keys = await caches.keys();
        await Promise.all(
          keys
            .filter((k) => /apex|hal-10|nr2-apex|overlay|glass/i.test(k))
            .map((k) => caches.delete(k))
        );
      }
    } catch (_) {}
    if (isEntry) {
      location.replace("/nr2-optical-beam-touch-mockup.html");
    }
  })();
})();

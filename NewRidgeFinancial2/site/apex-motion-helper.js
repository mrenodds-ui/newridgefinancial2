/**
 * NR2-Apex Motion Helper — reduced-motion gate, scan sweep, glitch, tilt, decoder, rollup
 * Build: hal-10340
 */
(function () {
  "use strict";

  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function triggerGlitch(element) {
    if (prefersReducedMotion || !element) return;
    element.classList.add("apex-glitch", "active");
    setTimeout(() => element.classList.remove("active"), 160);
  }

  function setUpdatingState(selector, isUpdating) {
    document.querySelectorAll(selector).forEach((el) => {
      el.classList.toggle("is-updating", !!isUpdating);
    });
  }

  function flashStage() {
    if (prefersReducedMotion) return;
    const main = document.getElementById("apex-main");
    if (!main) return;
    main.classList.add("is-glitching");
    setTimeout(() => main.classList.remove("is-glitching"), 200);
  }

  function animateValue(el, start, end, duration, formatter) {
    if (!el) return;
    const fmt = formatter || ((n) => String(n));
    if (prefersReducedMotion || !Number.isFinite(start) || !Number.isFinite(end)) {
      el.textContent = fmt(end);
      return;
    }
    const startTime = performance.now();
    function update(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = start + (end - start) * eased;
      el.textContent = fmt(current);
      if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
  }

  function decodeText(element, finalText, charset) {
    if (!element) return;
    const text = String(finalText == null ? "" : finalText);
    if (prefersReducedMotion) {
      element.textContent = text;
      return;
    }
    const chars = charset || "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    let iterations = 0;
    const interval = setInterval(() => {
      element.textContent = text
        .split("")
        .map((char, idx) => {
          if (idx < iterations) return text[idx];
          if (char === " " || char === "\n") return char;
          return chars[Math.floor(Math.random() * chars.length)];
        })
        .join("");
      if (iterations >= text.length) clearInterval(interval);
      iterations += 1 / 3;
    }, 40);
  }

  function enableHoloTilt(root) {
    if (prefersReducedMotion || !root) return;
    const cards = root.querySelectorAll(".apex-widget.apex-inst");
    cards.forEach((card) => {
      if (card.dataset.holoBound) return;
      card.dataset.holoBound = "1";
      card.classList.add("apex-holo-tilt");
      card.addEventListener("mousemove", (ev) => {
        const r = card.getBoundingClientRect();
        const px = (ev.clientX - r.left) / r.width - 0.5;
        const py = (ev.clientY - r.top) / r.height - 0.5;
        const rx = (py * -5).toFixed(2);
        const ry = (px * 5).toFixed(2);
        card.style.transform = `perspective(800px) rotateX(${rx}deg) rotateY(${ry}deg)`;
      });
      card.addEventListener("mouseleave", () => {
        card.style.transform = "";
      });
    });
  }

  function boot() {
    if (!prefersReducedMotion) {
      document.body.classList.add("apex-scan-sweep");
    } else {
      document.querySelectorAll(".apex-grid-floor").forEach((el) => el.remove());
    }
  }

  window.ApexMotion = {
    prefersReducedMotion,
    triggerGlitch,
    setUpdatingState,
    flashStage,
    animateValue,
    decodeText,
    enableHoloTilt,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();

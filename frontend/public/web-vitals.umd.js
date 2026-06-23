/*
 * web-vitals UMD bundle (https://github.com/GoogleChrome/web-vitals)
 * Place in public/ so it can be loaded in Playwright tests.
 */
// Minimal stub for Playwright perf test. In real use, replace with actual web-vitals.umd.js
window.webVitals = {
  getLCP: (cb) => setTimeout(() => cb({ value: 1200 }), 10),
  getCLS: (cb) => setTimeout(() => cb({ value: 0.05 }), 10),
  getINP: (cb) => setTimeout(() => cb({ value: 80 }), 10),
};

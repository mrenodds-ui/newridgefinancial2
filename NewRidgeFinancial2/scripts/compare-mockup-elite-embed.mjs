#!/usr/bin/env node
/**
 * Compare elite mock HTML on disk vs PAGE_META widget keys + structure signatures.
 * Usage: node scripts/compare-mockup-elite-embed.mjs [page-id]
 *
 * Expected keys always come from PAGE_META (not runtime PAGES.widgets, which is
 * intentionally empty in mock-embed staff mode).
 */
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const eliteDir = join(root, "..", ".local_logs", "moonshot_financial_eval", "page_mockups_elite");
const require = createRequire(import.meta.url);

globalThis.NR2_STAFF_MOCK_ONLY = true;
require(join(root, "site/data/mockup-elite-pages.js"));
require(join(root, "site/moonshot-page-registry.js"));

const onlyPage = process.argv[2] || null;

const STRUCTURE_SIG = [
  "widget-grid",
  "alert-ticker",
  "kpi-hero-row",
  "kpi-hero-tile",
  "ms-panel",
  "chart-container",
  "gauge-wrap",
  "canvas-table",
  "stat-grid",
];

/** HAL elite mock is a full widget mosaic; extras beyond PAGE_META are expected. */
const ALLOW_ELITE_EXTRAS = new Set(["hal"]);

function widgetKeysFromHtml(html) {
  const re = /data-hal-widget-key="([^"]+)"/g;
  const keys = [];
  let m;
  while ((m = re.exec(html))) keys.push(m[1]);
  return keys;
}

function metaWidgetKeys(pageId) {
  if (typeof PageSchema.pageMetaWidgets === "function") {
    const keys = PageSchema.pageMetaWidgets(pageId);
    if (keys.length) return keys;
  }
  const registrySrc = readFileSync(join(root, "site/moonshot-page-registry.js"), "utf8");
  const pageRe = new RegExp(
    `(?:^|\\n)\\s*(?:"${pageId}"|${pageId})\\s*:\\s*\\{([\\s\\S]*?)\\n\\s*\\},?\\n\\s*(?:"|[a-zA-Z]|\\})`,
    "m",
  );
  const pageBlock = registrySrc.match(pageRe);
  if (!pageBlock) return [];
  const widgetsBlock = pageBlock[1].match(/\bwidgets:\s*\[([\s\S]*?)\]/);
  if (!widgetsBlock) return [];
  return [...widgetsBlock[1].matchAll(/key:\s*"([^"]+)"/g)].map((x) => x[1]);
}

const pageIds = onlyPage ? [onlyPage] : PageSchema.STAFF_PAGE_IDS || [];

let failures = 0;
const rows = [];

for (const pageId of pageIds) {
  const path = join(eliteDir, `${pageId}.html`);
  if (!existsSync(path)) {
    console.warn(`SKIP ${pageId}: no elite HTML`);
    continue;
  }
  const html = readFileSync(path, "utf8");
  const eliteKeys = widgetKeysFromHtml(html);
  const expectedKeys = metaWidgetKeys(pageId);
  const missing = expectedKeys.filter((k) => !eliteKeys.includes(k));
  const extra = eliteKeys.filter((k) => !expectedKeys.includes(k));
  const dupes = eliteKeys.filter((k, i) => eliteKeys.indexOf(k) !== i);
  const sigHits = STRUCTURE_SIG.filter((s) => html.includes(s));
  const extrasFail = extra.length > 0 && expectedKeys.length > 0 && !ALLOW_ELITE_EXTRAS.has(pageId);

  if (missing.length) {
    console.error(`FAIL ${pageId}: elite HTML missing widget keys: ${missing.join(", ")}`);
    failures += 1;
  }
  if (extrasFail) {
    console.error(`FAIL ${pageId}: elite HTML extra widget keys: ${extra.join(", ")}`);
    failures += 1;
  }
  if (dupes.length) {
    console.error(`FAIL ${pageId}: duplicate widget keys: ${[...new Set(dupes)].join(", ")}`);
    failures += 1;
  }

  rows.push({
    pageId,
    eliteKeys: eliteKeys.length,
    expectedKeys: expectedKeys.length,
    signatures: sigHits.length,
    ok: !missing.length && !extrasFail && !dupes.length,
  });
}

console.log("\nElite embed parity checklist:");
console.log("pageId".padEnd(16), "widgets".padEnd(10), "expected".padEnd(10), "structure", "status");
for (const r of rows) {
  console.log(
    r.pageId.padEnd(16),
    String(r.eliteKeys).padEnd(10),
    String(r.expectedKeys).padEnd(10),
    String(r.signatures).padEnd(10),
    r.ok ? "OK" : "FAIL",
  );
}

assert.equal(failures, 0, `${failures} elite embed parity failure(s)`);
console.log(`\nelite embed compare OK — ${rows.length} page(s)`);

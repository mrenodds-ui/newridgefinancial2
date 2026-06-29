#!/usr/bin/env node
/**
 * Validate approved mockup pages have been converted into real functional pages.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const siteDir = join(__dirname, "site");
const require = createRequire(import.meta.url);

process.env.NR2_LOAD_IMPORTS = "1";

const appJs = readFileSync(join(siteDir, "app.js"), "utf8");
const indexHtml = readFileSync(join(siteDir, "index.html"), "utf8");

require(join(siteDir, "empty-states.js"));
require(join(siteDir, "import-loader.js"));
require(join(siteDir, "components.js"));
require(join(siteDir, "services.js"));
const PageViews = require(join(siteDir, "page-views.js"));
const halData = JSON.parse(readFileSync(join(siteDir, "data", "hal-manager.json"), "utf8"));

const FUNCTIONAL_PAGES = [
  { id: "financial", checks: ["pv-fin-top", "pv-bento--financial", "Production MTD"] },
  { id: "softdent", checks: ["pv-bento--softdent", "DAYSHEET A/R"] },
  { id: "quickbooks", checks: ["pv-bento--quickbooks", "P&amp;L Summary"] },
  { id: "ar", checks: ["pv-bento--ar", "Aging Buckets"] },
  { id: "claims", checks: ["pv-claims-layout", "Claims pipeline"] },
  { id: "narratives", checks: ["pv-two-pane--narratives", "Narrative Composer", "Draft Narrative Preview"] },
  { id: "documents", checks: ["pv-bento--documents", "Document Intake", "Selected Document Preview"] },
  { id: "library", checks: ["pv-library-layout", "Document Library"] },
];

for (const page of FUNCTIONAL_PAGES) {
  assert.ok(PageViews.hasPage(page.id), `${page.id} page must be routable`);
  const html = await PageViews.previewPageHtml(halData, page.id);
  assert.ok(!html.includes("pv--mock-image"), `${page.id} must NOT render a mockup image`);
  assert.ok(html.includes("pv--app"), `${page.id} must render the functional app surface`);
  assert.ok(html.includes("pv__header"), `${page.id} must use the shared page header`);
  assert.ok(
    html.includes("pv-badge--import") || html.includes("No data loaded") || html.includes("Import data"),
    `${page.id} must label import or empty data honestly`,
  );
  for (const check of page.checks) {
    assert.ok(html.includes(check), `${page.id} must include ${check}`);
  }
  if (page.id === "financial") {
    assert.ok(html.includes("Dr. Adams"), "financial page must show imported provider rows");
    assert.ok(html.includes("Hygiene Team"), "financial page must preserve non-doctor provider rows");
  }
}

assert.equal(PageViews.hasPage("hal"), false, "HAL must route to the real HAL command-center renderer");

assert.ok(!appJs.includes("/api/"), "app.js must not reference backend API routes");
assert.ok(indexHtml.includes('id="appPage"'), "index must have app page container");
assert.ok(indexHtml.includes('id="halPageRoot"'), "index must have HAL root container");
assert.ok(!indexHtml.includes("page-sample-data.js"), "index must not load mock sample data");
assert.ok(!appJs.includes("Kiera Serrano"), "must not use fake operator name");

console.log("page validation passed");

#!/usr/bin/env node
/**
 * Validate program pages render the original mockup PNG surfaces (exact look).
 */
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const siteDir = join(__dirname, "site");
const require = createRequire(import.meta.url);

const appJs = readFileSync(join(siteDir, "app.js"), "utf8");
const indexHtml = readFileSync(join(siteDir, "index.html"), "utf8");

require(join(siteDir, "page-sample-data.js"));
require(join(siteDir, "components.js"));
require(join(siteDir, "services.js"));
const PageViews = require(join(siteDir, "page-views.js"));
const halData = JSON.parse(readFileSync(join(siteDir, "data", "hal-manager.json"), "utf8"));

const MOCK_IMAGE_PAGES = {
  financial: "pages/01-financial-dashboard.png",
  softdent: "pages/02-softdent.png",
  quickbooks: "pages/03-quickbooks.png",
  ar: "pages/04-ar-collections.png",
  claims: "pages/05-claims-workbench.png",
  narratives: "pages/06-insurance-narratives.png",
  documents: "pages/07-accounting-documents.png",
  library: "pages/08-document-library.png",
  hal: "pages/09-hal-command-center.png",
};

function mockContainer() {
  let html = "";
  return {
    get innerHTML() {
      return html;
    },
    set innerHTML(value) {
      html = value;
    },
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
  };
}

for (const [id, png] of Object.entries(MOCK_IMAGE_PAGES)) {
  assert.ok(PageViews.hasPage(id), `missing page: ${id}`);
  assert.ok(existsSync(join(siteDir, png)), `mockup PNG missing on disk: ${png}`);

  const container = mockContainer();
  PageViews.renderPageView(container, halData, id, () => {});
  assert.ok(container.innerHTML.includes(`pv--${id}`), `${id} must render a page-specific surface`);
  assert.ok(container.innerHTML.includes("pv--mock-image"), `${id} must render the mockup image surface`);
  assert.ok(container.innerHTML.includes("<img"), `${id} must render an <img>`);
  assert.ok(container.innerHTML.includes(png), `${id} must point at ${png}`);
  assert.ok(container.innerHTML.includes("pv-mock-nav"), `${id} must include the navigation overlay`);
}

assert.ok(!appJs.includes("/api/"), "app.js must not reference backend API routes");
assert.ok(indexHtml.includes('id="appPage"'), "index must have app page container");
assert.ok(indexHtml.includes('id="halPageRoot"'), "index must have HAL root container");
assert.ok(!indexHtml.includes("Kiera Serrano"), "must not use fake operator name");

console.log("page validation passed");

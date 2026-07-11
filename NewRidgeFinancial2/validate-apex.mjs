#!/usr/bin/env node
/**
 * Apex Bridge launch validators (replaces mockup-era validate-pages/hal for Start Program).
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const siteDir = join(__dirname, "site");
const indexHtml = readFileSync(join(siteDir, "index.html"), "utf8");
const buildManifest = JSON.parse(readFileSync(join(__dirname, "nr2-build.json"), "utf8"));
const expected = String(buildManifest.assetVersion || buildManifest.BUILD_ID || "");

assert.ok(expected, "nr2-build.json must declare assetVersion or BUILD_ID");
assert.ok(indexHtml.includes('data-nr2-epoch="nr2-apex"'), "index must declare nr2-apex epoch");
assert.ok(indexHtml.includes('class="apex-bridge"') || indexHtml.includes("apex-bridge"), "index must use Apex bridge shell");
assert.ok(indexHtml.includes(`data-apex-version="${expected}"`), `index data-apex-version must be ${expected}`);

const requiredAssets = [
  "apex-tokens.css",
  "apex-animations.css",
  "apex-bridge.css",
  "apex-theme.css",
  "apex-chrome-flash.css",
  "apex-hal-brain.css",
  "apex-core.js",
  "apex-ticker.js",
  "apex-hal-bridge.js",
  "apex-hal-brain.js",
  "apex-narratives.js",
  "apex-chart-widget.js",
  "apex-motion-helper.js",
];

for (const name of requiredAssets) {
  assert.ok(existsSync(join(siteDir, name)), `missing Apex asset: ${name}`);
  assert.ok(indexHtml.includes(`${name}?v=${expected}`), `index must load ${name}?v=${expected}`);
}

const pages = [
  "financial",
  "taxes",
  "softdent",
  "quickbooks",
  "ar",
  "claims",
  "narratives",
  "documents",
  "library",
  "office-manager",
  "hal",
];
for (const page of pages) {
  assert.ok(indexHtml.includes(`data-page="${page}"`), `index nav must include ${page}`);
}

assert.ok(indexHtml.includes('id="apex-subnav"'), "index must include Apex subnav");
assert.ok(indexHtml.includes('id="apex-stage"'), "index must include Apex stage");

const siteManifest = JSON.parse(readFileSync(join(siteDir, "nr2-build.json"), "utf8"));
assert.equal(String(siteManifest.assetVersion || siteManifest.BUILD_ID || ""), expected, "site/nr2-build.json must match root nr2-build.json");

console.log(`validate-apex.mjs ok (${expected})`);

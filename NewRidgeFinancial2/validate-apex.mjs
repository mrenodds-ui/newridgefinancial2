#!/usr/bin/env node
/**
 * NR2 clean-slate launch validators (nr2-11000-clean).
 * Proves overlays/packs/legacy apex shell are gone before Start Program.
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const siteDir = join(__dirname, "site");
const indexHtml = readFileSync(join(siteDir, "index.html"), "utf8");
const buildManifest = JSON.parse(readFileSync(join(__dirname, "nr2-build.json"), "utf8"));
const expected = String(buildManifest.assetVersion || buildManifest.BUILD_ID || "");

assert.ok(expected, "nr2-build.json must declare assetVersion or BUILD_ID");
assert.equal(expected, "nr2-11000-clean", "clean-slate build stamp must be nr2-11000-clean");
assert.equal(String(buildManifest.staffRenderMode || ""), "nr2-clean");
assert.equal(buildManifest.compat, false);
assert.equal(buildManifest.packsAllowed, false);

assert.ok(indexHtml.includes('data-nr2-epoch="nr2-clean"'), "index must declare nr2-clean epoch");
assert.ok(indexHtml.includes('data-build-id="nr2-11000-clean"'), "index must declare clean build id");
assert.ok(indexHtml.includes('name="build-id" content="nr2-11000-clean"'), "index meta build-id required");
assert.ok(indexHtml.includes("NR2_CLEAN_SLATE"), "index must set clean-slate guard");
assert.ok(indexHtml.includes(`nr2-entry.js?v=${expected}`), `index must load nr2-entry.js?v=${expected}`);
assert.ok(indexHtml.includes(`nr2-tokens.css?v=${expected}`), `index must load nr2-tokens.css?v=${expected}`);
assert.ok(existsSync(join(siteDir, "nr2-entry.js")), "missing nr2-entry.js");
assert.ok(existsSync(join(siteDir, "nr2-tokens.css")), "missing nr2-tokens.css");

const bannedApexAssets = [
  "apex-tokens.css",
  "apex-animations.css",
  "apex-bridge.css",
  "apex-hal-brain.css",
  "apex-core.js",
  "apex-ticker.js",
  "apex-hal-bridge.js",
  "apex-hal-brain.js",
  "apex-narratives.js",
  "apex-chart-widget.js",
  "apex-motion-helper.js",
  "apex-quarantine-panel.js",
  "sw.js",
  "app.js",
  "desktop-boot.js",
  "desktop-bridge.js",
  "widget-contract.js",
  "import-loader.js",
];

for (const name of bannedApexAssets) {
  assert.ok(!indexHtml.includes(name), `index must not load cremated asset: ${name}`);
  assert.ok(!existsSync(join(siteDir, name)), `cremated asset must be absent from site/: ${name}`);
}

assert.ok(!indexHtml.includes("apex-bridge"), "index must not use apex-bridge shell");
assert.ok(!indexHtml.includes("data-apex-version"), "index must not declare data-apex-version");
assert.ok(!indexHtml.includes('data-nr2-epoch="nr2-apex"'), "index must not keep nr2-apex epoch");

const packs = readdirSync(__dirname).filter((n) => /^apex_.*_pack\.py$/.test(n));
assert.equal(packs.length, 0, `apex_*_pack.py must be zero on runtime path; found: ${packs.join(",")}`);

const siteManifest = JSON.parse(readFileSync(join(siteDir, "nr2-build.json"), "utf8"));
assert.equal(
  String(siteManifest.assetVersion || siteManifest.BUILD_ID || ""),
  expected,
  "site/nr2-build.json must match root nr2-build.json"
);

console.log(`validate-apex.mjs ok (${expected})`);

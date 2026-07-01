#!/usr/bin/env node
/**
 * Bump NR2 build version across manifest, page schema, and index.html cache busts.
 *
 * Usage:
 *   node scripts/bump-nr2-build.mjs hal-95
 *   node scripts/bump-nr2-build.mjs          # auto-increment hal-NN
 */
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(__dirname, "..");
const nr2Dir = join(repoRoot, "NewRidgeFinancial2");
const manifestPath = join(nr2Dir, "nr2-build.json");
const siteManifestPath = join(nr2Dir, "site", "nr2-build.json");
const indexPath = join(nr2Dir, "site", "index.html");
const schemaPath = join(nr2Dir, "site", "page-schema.js");

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function writeJson(path, data) {
  writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`, "utf8");
}

function nextHalVersion(current) {
  const match = String(current || "").match(/^hal-(\d+)$/);
  if (!match) throw new Error(`Cannot auto-increment version "${current}". Pass hal-NN explicitly.`);
  const n = Number(match[1]) + 1;
  return `hal-${n}`;
}

function replaceVersionInIndex(html, fromVersion, toVersion) {
  if (fromVersion === toVersion) return html;
  const from = `?v=${fromVersion}`;
  const to = `?v=${toVersion}`;
  assert.ok(html.includes(from), `index.html does not contain ${from}`);
  return html.split(from).join(to);
}

function replaceSchemaVersion(js, toVersion) {
  return js.replace(/const SCHEMA_VERSION = "[^"]+";/, `const SCHEMA_VERSION = "${toVersion}";`);
}

const manifest = readJson(manifestPath);
const currentVersion = manifest.schemaVersion || manifest.assetVersion;
const targetVersion = process.argv[2] ? String(process.argv[2]) : nextHalVersion(currentVersion);

if (!/^hal-\d+$/.test(targetVersion)) {
  throw new Error(`Invalid version "${targetVersion}". Expected format hal-NN.`);
}

const builtAt = new Date().toISOString();
const nextManifest = {
  ...manifest,
  assetVersion: targetVersion,
  schemaVersion: targetVersion,
  builtAt,
};

writeJson(manifestPath, nextManifest);
writeJson(siteManifestPath, {
  ...nextManifest,
  notes: "Mirror of ../nr2-build.json — served to the UI over the local HTTP server.",
});

const indexHtml = readFileSync(indexPath, "utf8");
writeFileSync(indexPath, replaceVersionInIndex(indexHtml, currentVersion, targetVersion), "utf8");

const schemaJs = readFileSync(schemaPath, "utf8");
writeFileSync(schemaPath, replaceSchemaVersion(schemaJs, targetVersion), "utf8");

console.log(`Bumped NR2 build ${currentVersion} -> ${targetVersion}`);
console.log("Updated:");
console.log(`  ${manifestPath}`);
console.log(`  ${siteManifestPath}`);
console.log(`  ${indexPath}`);
console.log(`  ${schemaPath}`);
console.log("");
console.log("Next:");
console.log("  cd NewRidgeFinancial2 && node validate-pages.mjs && node validate-hal.mjs");
console.log("  Restart Start Program");

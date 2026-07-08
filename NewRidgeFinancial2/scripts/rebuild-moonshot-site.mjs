#!/usr/bin/env node
/**
 * Rebuild NR2 site/ to the Moonshot schema bundle only.
 * - Validates manifest files exist
 * - Ensures index.html script list matches manifest
 * - Removes orphan assets under site/ not in the manifest
 */
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync, unlinkSync, rmdirSync, existsSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const siteDir = join(root, "site");
const manifestPath = join(root, "moonshot-site.manifest.json");
const wsManifestPath = join(root, "workstation-site.manifest.json");
const buildPath = join(root, "nr2-build.json");
const dryRun = process.argv.includes("--dry-run");

const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
const wsManifest = existsSync(wsManifestPath)
  ? JSON.parse(readFileSync(wsManifestPath, "utf8"))
  : { workstation: [] };
const build = JSON.parse(readFileSync(buildPath, "utf8"));
const version = build.assetVersion || build.BUILD_ID;

const allowed = new Set(
  [...manifest.shell, ...manifest.scripts, ...manifest.data, ...(wsManifest.workstation || [])].map((p) =>
    p.replace(/\\/g, "/"),
  ),
);

function normalize(relPath) {
  return relPath.replace(/\\/g, "/");
}

function walk(dir, acc = []) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) walk(full, acc);
    else acc.push(relative(siteDir, full));
  }
  return acc;
}

const indexHtml = readFileSync(join(siteDir, "index.html"), "utf8");
const scriptSrcs = [...indexHtml.matchAll(/<script src="([^"?]+)/g)].map((m) => m[1]);
for (const src of scriptSrcs) {
  assert.ok(manifest.scripts.includes(src), `index.html loads ${src} but it is missing from moonshot-site.manifest.json`);
}
assert.equal(scriptSrcs.length, manifest.scripts.length, "index.html script count must match manifest.scripts");

for (const rel of [...manifest.shell, ...manifest.scripts, ...manifest.data, ...(wsManifest.workstation || [])]) {
  const full = join(siteDir, rel);
  assert.ok(existsSync(full), `manifest file missing on disk: ${rel}`);
}

const orphans = [];
for (const rel of walk(siteDir)) {
  const norm = normalize(rel);
  if (allowed.has(norm)) continue;
  orphans.push(rel);
}

if (orphans.length) {
  console.log(dryRun ? "[dry-run] Would remove orphans:" : "Removing orphans:");
  for (const rel of orphans.sort()) {
    console.log(`  - ${normalize(rel)}`);
    if (!dryRun) unlinkSync(join(siteDir, rel));
  }
}

if (!dryRun) {
  const pagesDir = join(siteDir, "pages");
  if (existsSync(pagesDir) && readdirSync(pagesDir).length === 0) {
    rmdirSync(pagesDir);
    console.log("Removed empty site/pages/");
  }
}

console.log(
  dryRun
    ? `Moonshot site dry-run OK — ${allowed.size} manifest files, ${orphans.length} orphan(s) would be removed (build ${version}).`
    : `Moonshot site rebuilt — ${allowed.size} manifest files kept, ${orphans.length} orphan(s) removed (build ${version}).`,
);

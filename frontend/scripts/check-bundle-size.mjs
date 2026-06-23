#!/usr/bin/env node
/**
 * Post-build bundle size guard.
 * Run via: node scripts/check-bundle-size.mjs
 * Or via:  npm run build:check
 *
 * Limits (uncompressed):
 *   - Any single JS chunk: 500 KB
 *   - Any single CSS file: 100 KB
 *   - Total JS across all chunks: 650 KB
 */
import { readdir, stat } from "node:fs/promises";
import { join, extname, basename } from "node:path";

const DIST_ASSETS = join(process.cwd(), "dist", "assets");

const LIMITS = {
  jsPerChunk: 500 * 1024,
  cssPerFile: 100 * 1024,
  jsTotalAll: 650 * 1024,
};

function humanize(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

let failed = false;
let totalJs = 0;

const entries = await readdir(DIST_ASSETS).catch(() => {
  console.error("dist/assets not found — run `npm run build` first.");
  process.exit(1);
});

console.log("\n📦  Bundle size report\n");
console.log(`${"File".padEnd(50)} ${"Size".padStart(10)}  ${"Limit".padStart(10)}  Status`);
console.log("─".repeat(85));

for (const name of entries.sort()) {
  const fullPath = join(DIST_ASSETS, name);
  const { size } = await stat(fullPath);
  const ext = extname(name);

  if (ext === ".js") totalJs += size;

  let limit = null;
  if (ext === ".js") limit = LIMITS.jsPerChunk;
  if (ext === ".css") limit = LIMITS.cssPerFile;
  if (limit === null) continue; // skip maps, etc.

  const over = size > limit;
  if (over) failed = true;
  const status = over ? "❌ OVER" : "✅";
  console.log(`${basename(name).padEnd(50)} ${humanize(size).padStart(10)}  ${humanize(limit).padStart(10)}  ${status}`);
}

console.log("─".repeat(85));
const totalOver = totalJs > LIMITS.jsTotalAll;
if (totalOver) failed = true;
console.log(
  `${"TOTAL JS".padEnd(50)} ${humanize(totalJs).padStart(10)}  ${humanize(LIMITS.jsTotalAll).padStart(10)}  ${totalOver ? "❌ OVER" : "✅"}`,
);
console.log();

if (failed) {
  console.error("❌  Bundle size limit exceeded. Reduce chunk size or raise the limit in scripts/check-bundle-size.mjs.\n");
  process.exit(1);
} else {
  console.log("✅  All bundle sizes within limits.\n");
}

#!/usr/bin/env node
/** Regenerate site/moonshot-page-layouts.js after editing the MOONSHOT_PAGE_LAYOUTS object. */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "site");
const src = join(root, "moonshot-page-layouts.js");
const mod = await import(pathToFileURL(src).href);
const layouts = mod.default || mod.MOONSHOT_PAGE_LAYOUTS || globalThis.MOONSHOT_PAGE_LAYOUTS;
const body = `/** Moonshot page panel layouts — inlined manifest (no external JSON). */
const MOONSHOT_PAGE_LAYOUTS = ${JSON.stringify(layouts, null, 2)};

if (typeof module !== "undefined" && module.exports) {
  module.exports = MOONSHOT_PAGE_LAYOUTS;
}
if (typeof globalThis !== "undefined") {
  globalThis.MOONSHOT_PAGE_LAYOUTS = MOONSHOT_PAGE_LAYOUTS;
}
if (typeof window !== "undefined") {
  window.MOONSHOT_PAGE_LAYOUTS = MOONSHOT_PAGE_LAYOUTS;
}
`;
writeFileSync(src, body);
console.log("Reformatted site/moonshot-page-layouts.js");

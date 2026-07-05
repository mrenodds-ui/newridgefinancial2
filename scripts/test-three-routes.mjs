import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const siteDir = path.join(process.cwd(), "NewRidgeFinancial2", "site");
const halData = JSON.parse(fs.readFileSync(path.join(siteDir, "data", "hal-manager.json")));
const halModels = JSON.parse(fs.readFileSync(path.join(siteDir, "data", "hal-models.json")));
const pages = [{ id: "hal", label: "HAL Command Center" }];

await import(pathToFileURL(path.join(siteDir, "hal-agent-programming.js")).href);
await import(pathToFileURL(path.join(siteDir, "hal-cursor-parity.js")).href);
const HalCore = (await import(pathToFileURL(path.join(siteDir, "hal-core.js")))).default;

globalThis._halInterviewMode = true;

const tests = [
  "how does handleHalSubmit work in app.js",
  "That's wrong — I meant imports, not widgets.",
  "What assumptions must staff verify before trusting widget totals?",
];

let ok = true;
for (const q of tests) {
  const r = HalCore.routeHalCommand(halData, halModels, pages, q);
  const page = HalCore.findPage(q.toLowerCase());
  console.log("Q:", q);
  console.log("  intent:", r.intent);
  console.log("  page:", page);
  console.log("  text:", String(r.text || "").slice(0, 100));
  if (q.includes("handleHalSubmit") && r.intent !== "capability:code-handleHalSubmit") ok = false;
  if (q.includes("wrong") && r.intent !== "capability:correction-imports") ok = false;
  if (q.includes("assumptions") && r.intent !== "capability:widget-trust-assumptions") ok = false;
  if (q.includes("handleHalSubmit") && page === "hal") ok = false;
}
process.exit(ok ? 0 : 1);

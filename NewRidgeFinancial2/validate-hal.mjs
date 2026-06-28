#!/usr/bin/env node
/**
 * HAL validation — JSON, router, firewall, registry, and suggestion routes.
 * Usage: node validate-hal.mjs
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const siteDir = join(__dirname, "site");
const require = createRequire(import.meta.url);

const halManagerPath = join(siteDir, "data", "hal-manager.json");
const halModelsPath = join(siteDir, "data", "hal-models.json");

function loadJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function main() {
  const halData = loadJson(halManagerPath);
  const halModels = loadJson(halModelsPath);
  const halCoreUrl = pathToFileURL(join(siteDir, "hal-core.js")).href;
  const HalCore = (await import(halCoreUrl)).default || (await import(halCoreUrl));

  const pages = [
    { id: "financial", label: "Financial dashboard", title: "Owner Financial Dashboard" },
    { id: "claims", label: "Claims Workbench", title: "Claims Workbench" },
    { id: "hal", label: "HAL Command Center", title: "HAL Command Center" },
  ];

  let passed = 0;

  // JSON structure
  assert(halData.registry && halData.registry.length === 9, "registry must have 9 entries");
  assert(halData.sources.items.length === 4, "sources must have 4 items");
  assert(halData.firewall.examples.length >= 4, "firewall examples required");
  passed++;

  // Firewall blocks external verbs before model
  const blocked = HalCore.routeHalCommand(halData, halModels, pages, "submit the claim");
  assert(blocked.intent === "blocked: firewall", "submit must be blocked");
  const blockedEmail = HalCore.routeHalCommand(halData, halModels, pages, "emailing the payer");
  assert(blockedEmail.intent === "blocked: firewall", "emailing must be blocked");
  const escalateSubmit = HalCore.routeHalCommand(halData, halModels, pages, "escalate and submit the claim");
  assert(escalateSubmit.intent === "blocked: firewall", "firewall must beat escalation");
  passed++;

  // Firewall simulator
  const allowed = HalCore.firewallVerdict("open claims workbench", halData.firewall);
  assert(allowed.allowed === true, "open claims should be allowed");
  const denied = HalCore.firewallVerdict("upload the narrative", halData.firewall);
  assert(denied.allowed === false, "upload should be blocked");
  passed++;

  // Suggestion routes from validation fixtures
  const routes = halData.validation.suggestionRoutes;
  for (const [suggestion, expectedIntent] of Object.entries(routes)) {
    const result = HalCore.routeHalCommand(halData, halModels, pages, suggestion);
    assert(
      result.intent === expectedIntent || result.intent.startsWith(expectedIntent),
      `suggestion "${suggestion}" expected ${expectedIntent}, got ${result.intent}`,
    );
  }
  passed++;

  // Registry grouping
  const lanes = HalCore.deriveReasoningLanes(halData);
  assert(lanes.length === 3, "reasoning lanes must be 3");
  const totalEntries = lanes.reduce((sum, lane) => sum + lane.count, 0);
  assert(totalEntries === halData.registry.length, "lane counts must match registry");
  passed++;

  // Model lane status derived from hal-models
  const cards = HalCore.deriveModelLaneCards(halModels);
  assert(cards.length === 3, "model lane cards must be 3");
  for (const card of cards) {
    const lane = halModels.lanes.find((l) => l.name === card.name);
    assert(lane && card.state === lane.state, `lane state drift for ${card.name}`);
  }
  passed++;

  // Page navigation
  const nav = HalCore.routeHalCommand(halData, halModels, pages, "open claims workbench");
  assert(nav.intent === "navigate: claims", "claims navigation");
  const explain = HalCore.routeHalCommand(halData, halModels, pages, "explain quickbooks");
  assert(explain.intent === "explain: quickbooks", "quickbooks explain");
  passed++;

  // cleanModelText strips thinking tags
  const cleaned = HalCore.cleanModelText("<think>secret</think>Visible answer");
  assert(cleaned === "Visible answer", "cleanModelText must strip thinking");
  passed++;

  // Session templates
  const sessionErrors = HalCore.validateSessionTemplates(halData);
  assert(sessionErrors.length === 0, "session templates invalid: " + sessionErrors.join("; "));
  assert(halData.workSessions.templates.length === 5, "must have 5 session templates");
  passed++;

  // Session routing
  const sessionRoutes = halData.validation.sessionRoutes || {};
  for (const [command, expectedIntent] of Object.entries(sessionRoutes)) {
    const result = HalCore.routeHalCommand(halData, halModels, pages, command);
    assert(result.intent === expectedIntent, `session "${command}" expected ${expectedIntent}, got ${result.intent}`);
  }
  passed++;

  // Session firewall trap
  const sessionTrap = HalCore.routeHalCommand(halData, halModels, pages, halData.validation.sessionFirewallTrap);
  assert(sessionTrap.intent === "blocked: firewall", "session + submit must be blocked");
  passed++;

  // Session state helpers
  const template = HalCore.sessionTemplateById(halData, "claims-review");
  const session = HalCore.createSessionState(template);
  assert(session.checklist.length === template.checklist.length, "session checklist length");
  const toggled = HalCore.toggleSessionCheck(session, 0);
  assert(toggled.checklist[0].done === true, "toggle check");
  const note = HalCore.draftHandoffNote(toggled, halData);
  assert(note.includes("human review"), "handoff note disclaimer");
  passed++;

  // app.js syntax
  const { execSync } = require("node:child_process");
  execSync("node --check site/app.js", { cwd: __dirname, stdio: "pipe" });
  execSync("node --check site/hal-core.js", { cwd: __dirname, stdio: "pipe" });
  passed++;

  console.log(`HAL validation passed (${passed} suites)`);
}

main().catch((error) => {
  console.error("HAL validation failed:", error.message);
  process.exit(1);
});

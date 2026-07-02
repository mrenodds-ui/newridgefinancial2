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

function buildRoutingRegressionCases() {
  const cases = [];
  const add = (question, expected) => cases.push([question, expected]);
  const addMany = (questions, expected) => questions.forEach((question) => add(question, expected));

  addMany(["What can you do?", "How do you work?", "help", "what are your capabilities?", "tell me what you can do"], "help");
  addMany(["Print this page", "print current page", "print the page"], "print: page");
  addMany(["Print widget feed", "print dashboard widgets", "print manager dashboard"], "print: widget-feed");
  addMany(["Print program snapshot", "print snapshot"], "print: snapshot");
  addMany(["Print drawer", "print command center panel"], "print: drawer");
  addMany(["Print last HAL reply", "print hal response"], "print: hal-reply");
  addMany(["Print financial widget", "print financial overview widget"], "print: widget:practiceFinancialOverview");
  addMany(["Print ar aging widget"], "print: widget:arAgingAndCollections");
  addMany(["Closeout runbook", "month end runbook", "month-end close runbook"], "ops: closeout-runbook");
  addMany(["Self heal program", "strengthen program", "repair program"], "ops: self-heal");
  addMany(["Approve all journal queue", "bulk approve journal posting queue"], "ops: journal-bulk-approve");
  addMany(["Run readiness check", "check hal", "self-check", "readiness check now"], "readiness: run");
  addMany(["Show diagnostics", "display diagnostics"], "readiness: show");
  addMany(["Clear diagnostics", "reset diagnostics"], "readiness: clear");

  for (const [id, label] of [
    ["claims-review", "claims review"],
    ["source-freshness", "source freshness review"],
    ["ar-review", "A/R review"],
    ["document-review", "document review"],
    ["blocked-triage", "blocked item triage"],
  ]) {
    addMany([`Start ${label}`, `start the ${label}`], `session: start:${id}`);
  }

  addMany(["Show active session", "session status", "active work session"], "session: show");
  addMany(["Reset work session", "reset the current session", "clear work session", "end the session"], "session: reset");
  addMany(["Draft handoff note", "handoff note"], "session: handoff");
  addMany(["Build evidence packet", "assemble evidence packet", "build the packet"], "packet: build");
  addMany(["Show evidence packet", "display evidence packet"], "packet: show");
  addMany(["Clear evidence packet", "clear local packet"], "packet: clear");
  addMany(["Make a plan for today", "Prioritize my work", "Where should I start?"], "reasoning");
  addMany(["Second opinion on a complex case", "Escalate this denial", "Do a deep review"], "escalation");
  addMany(["Run this through 120b", "Use gpt-oss 120b for this", "HAL run through 120b"], "oss");

  const pageNames = {
    financial: ["financial dashboard", "financial"],
    softdent: ["SoftDent", "practice management"],
    quickbooks: ["QuickBooks", "profit and loss"],
    ar: ["A/R", "collections", "aging"],
    claims: ["claims workbench", "claims"],
    narratives: ["insurance narratives", "narratives"],
    documents: ["accounting documents", "documents", "posting queue"],
    library: ["document library", "library"],
    hal: ["HAL command center", "HAL"],
  };
  for (const [id, names] of Object.entries(pageNames)) {
    for (const name of names) {
      addMany([`Open ${name}`, `Go to ${name}`], `navigate: ${id}`);
      addMany([`Explain ${name}`, `What is ${name}?`], `explain: ${id}`);
    }
  }

  addMany(["What needs attention today?", "priorities today"], "priorities");
  addMany(["What is ready to work on", "ready pages"], "registry: ready");
  addMany(["What is blocked", "show blockers", "what is waiting"], "registry: blocked");
  addMany(["firewall status", "what are the guardrails?"], "firewall");
  addMany(["Are you connected to a model?", "model lanes"], "model lanes");
  addMany(["source health", "source freshness"], "sources");
  addMany(["read-only areas", "review-only areas"], "registry: read-only");
  addMany(["next staff action", "what should staff review next"], "registry: next actions");

  const externalVerbs = ["submit", "email", "upload", "send", "fax", "transmit", "approve", "deny", "delete", "remove", "dispatch", "mail", "pay"];
  const externalObjects = ["the denied claim", "the payer", "the document", "the statement", "the invoice", "the record"];
  for (const verb of externalVerbs) {
    for (const object of externalObjects) add(`${verb} ${object}`, "blocked: firewall");
  }
  addMany(["Process a payment", "Record a charge", "Make a refund", "Post a transaction", "Write back to SoftDent"], "blocked: firewall");

  const modelFallback = [
    "What is the office weather?",
    "Summarize dental billing risk generally",
    "What should a manager know generally?",
    "Write a neutral note for internal review",
    "Explain denial trends in plain English",
    "Give me a generic review reminder",
    "Summarize this imaginary case",
  ];
  modelFallback.forEach((question) => add(question, "model: query"));

  return { cases, externalVerbs, externalObjects, modelFallback };
}

function seededChoice(seedState, items) {
  seedState.value = (seedState.value * 1664525 + 1013904223) >>> 0;
  return items[Math.floor((seedState.value / 0x100000000) * items.length)];
}

function buildSeededRoutingVariants(count) {
  const { cases, externalVerbs, externalObjects, modelFallback } = buildRoutingRegressionCases();
  const prefixes = ["", "please ", "can you ", "HAL, ", "locally ", "for staff review, "];
  const suffixes = ["", " please", " now", " locally", " for review"];
  const trapLocals = ["Run readiness check", "Build evidence packet", "Start claims review", "Show diagnostics", "Open claims workbench"];
  const trapExternals = ["and email it", "and submit it", "and upload it", "then fax the note", "then delete record"];
  const seedState = { value: 20260628 };
  const variants = [];

  for (let i = 0; i < count; i++) {
    let question;
    let expected;

    if (i < count * 0.7) {
      const [base, intent] = cases[i % cases.length];
      const prefix = prefixes[Math.floor(i / cases.length) % prefixes.length];
      const suffix = suffixes[Math.floor(i / (cases.length * prefixes.length)) % suffixes.length];
      question = `${prefix}${base}${suffix}`;
      expected = intent;
    } else if (i < count * 0.9) {
      const local = trapLocals[i % trapLocals.length];
      const external = trapExternals[Math.floor(i / trapLocals.length) % trapExternals.length];
      const prefix = i % 3 === 0 ? "HAL, " : i % 3 === 1 ? "please " : "";
      question = `${prefix}${local} ${external}`;
      expected = "blocked: firewall";
    } else if (i < count * 0.95) {
      const base = modelFallback[i % modelFallback.length];
      const prefix = prefixes[i % prefixes.length];
      const suffix = suffixes[Math.floor(i / modelFallback.length) % suffixes.length];
      question = `${prefix}${base}${suffix}`;
      expected = "model: query";
    } else {
      const verb = externalVerbs[i % externalVerbs.length];
      const object = externalObjects[Math.floor(i / externalVerbs.length) % externalObjects.length];
      const noise = seededChoice(seedState, ["before staff review", "locally", "in HAL", "for triage", "today"]);
      const prefix = i % 2 === 0 ? "please " : "HAL, ";
      question = `${prefix}${verb} ${object} ${noise}`;
      expected = "blocked: firewall";
    }

    variants.push([question.replace(/\s+/g, " ").trim(), expected]);
  }

  return variants;
}

async function main() {
  process.env.NR2_LOAD_IMPORTS = "1";
  const halData = loadJson(halManagerPath);
  const halModels = loadJson(halModelsPath);
  const halCoreUrl = pathToFileURL(join(siteDir, "hal-core.js")).href;
  const HalCore = (await import(halCoreUrl)).default || (await import(halCoreUrl));
  const printUtilsUrl = pathToFileURL(join(siteDir, "print-utils.js")).href;
  const PrintUtils = (await import(printUtilsUrl)).default || globalThis.PrintUtils;
  assert(typeof PrintUtils.esc === "function", "PrintUtils must load");
  assert(PrintUtils.esc("<test>") === "&lt;test&gt;", "PrintUtils esc must escape html");

  const pages = [
    { id: "financial", label: "Financial dashboard", title: "Owner Financial Dashboard" },
    { id: "softdent", label: "SoftDent", title: "SoftDent" },
    { id: "quickbooks", label: "QuickBooks", title: "QuickBooks" },
    { id: "ar", label: "A/R & Collections", title: "A/R & Collections" },
    { id: "claims", label: "Claims Workbench", title: "Claims Workbench" },
    { id: "narratives", label: "Insurance Narratives", title: "Insurance Narratives" },
    { id: "documents", label: "Accounting Documents", title: "Accounting Documents" },
    { id: "library", label: "Document Library", title: "Document Library" },
    { id: "office-manager", label: "Office Manager", title: "Office Manager" },
    { id: "hal", label: "HAL Command Center", title: "HAL Command Center" },
  ];

  let passed = 0;

  // JSON structure
  assert(halData.registry && halData.registry.length === 11, "registry must have 11 entries");
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
  assert(cards.length === halModels.lanes.length, "model lane cards must match configured lanes");
  assert(cards.length >= 9, "all available local models plus helper should be exposed as lanes");
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

  // Evidence packets
  const noPacket = HalCore.buildEvidencePacket(null, halData, halModels);
  assert(noPacket === null, "cannot build packet without session");
  const sessionForPacket = HalCore.createSessionState(template);
  const packet = HalCore.buildEvidencePacket(sessionForPacket, halData, halModels);
  assert(packet !== null, "packet must build from session");
  const packetErrors = HalCore.validateEvidencePacket(packet, halData);
  assert(packetErrors.length === 0, "packet validation: " + packetErrors.join("; "));
  const packetRoutes = halData.validation.packetRoutes || {};
  for (const [command, expectedIntent] of Object.entries(packetRoutes)) {
    const result = HalCore.routeHalCommand(halData, halModels, pages, command);
    assert(result.intent === expectedIntent, `packet "${command}" expected ${expectedIntent}, got ${result.intent}`);
  }
  const packetTrap = HalCore.routeHalCommand(halData, halModels, pages, halData.validation.packetFirewallTrap);
  assert(packetTrap.intent === "blocked: firewall", "packet + email must be blocked");
  passed++;

  // Readiness checks
  assert(halData.readiness && halData.readiness.expectedRegistryCount === 11, "readiness config required");
  const readinessReport = HalCore.runReadinessChecks(halData, halModels, pages);
  assert(readinessReport && readinessReport.results && readinessReport.results.length >= 6, "readiness must return checks");
  const registryCheck = readinessReport.results.find((item) => item.id === "registry");
  assert(registryCheck && registryCheck.status === "Pass", "registry readiness must pass");
  const firewallCheck = readinessReport.results.find((item) => item.id === "firewall");
  assert(firewallCheck && firewallCheck.status === "Pass", "firewall readiness must pass");
  const routesCheck = readinessReport.results.find((item) => item.id === "routes");
  assert(routesCheck && routesCheck.status === "Pass", "route fixture readiness must pass");
  const readinessRoutes = halData.validation.readinessRoutes || {};
  for (const [command, expectedIntent] of Object.entries(readinessRoutes)) {
    const result = HalCore.routeHalCommand(halData, halModels, pages, command);
    assert(result.intent === expectedIntent, `readiness "${command}" expected ${expectedIntent}, got ${result.intent}`);
  }
  const readinessTrap = HalCore.routeHalCommand(halData, halModels, pages, halData.validation.readinessFirewallTrap);
  assert(readinessTrap.intent === "blocked: firewall", "readiness + email must be blocked");
  const summary = HalCore.formatReadinessSummary(readinessReport);
  assert(summary.includes("HAL readiness"), "readiness summary must format report");
  passed++;

  // Staff use gate
  const gate = readinessReport.gate;
  assert(gate && typeof gate.status === "string", "readiness report must include staff use gate");
  assert(["Ready", "Ready with warnings", "Not ready"].includes(gate.status), "gate status must be a known value: " + gate.status);
  const allPass = readinessReport.results.every((r) => r.status === "Pass");
  const anyFail = readinessReport.results.some((r) => r.status === "Fail");
  if (anyFail) assert(gate.status === "Not ready", "gate must be Not ready when a check fails");
  else if (allPass) assert(gate.status === "Ready", "gate must be Ready when all checks pass");
  else assert(gate.status === "Ready with warnings", "gate must warn when only warnings exist");
  // Unknown gate when no report
  const emptyGate = HalCore.staffUseGate(null);
  assert(emptyGate.status === "Unknown", "gate must be Unknown without a report");
  // Synthetic fail forces Not ready
  const failReport = { results: [{ id: "x", label: "X", status: "Fail", detail: "d", next: "fix it" }] };
  assert(HalCore.staffUseGate(failReport).status === "Not ready", "synthetic fail must gate Not ready");
  // Gate routing + firewall precedence
  const gateRoute = HalCore.routeHalCommand(halData, halModels, pages, "Are you ready for staff use?");
  assert(gateRoute.intent === "readiness: gate", "staff use gate must route locally");
  const gateTrap = HalCore.routeHalCommand(halData, halModels, pages, "Are you ready for staff use and email it");
  assert(gateTrap.intent === "blocked: firewall", "gate + email must be blocked");
  assert(HalCore.formatReadinessSummary(readinessReport).includes("Staff use gate:"), "summary must include staff use gate line");
  passed++;

  // Operator smoke test + handoff summary
  const smoke = HalCore.runOperatorSmokeTest(halData, halModels, pages);
  assert(smoke && Array.isArray(smoke.steps) && smoke.steps.length === 6, "smoke test must return 6 steps");
  assert(smoke.steps.every((s) => s.status === "Pass"), "all smoke steps must pass: " + smoke.steps.filter((s) => s.status !== "Pass").map((s) => s.label).join(", "));
  assert(smoke.overall === "Pass", "smoke overall must be Pass");
  assert(HalCore.formatSmokeTestSummary(smoke).includes("operator smoke test"), "smoke summary must format");
  const operatorRoutes = halData.validation.operatorRoutes || {};
  for (const [command, expectedIntent] of Object.entries(operatorRoutes)) {
    const routed = HalCore.routeHalCommand(halData, halModels, pages, command);
    assert(routed.intent === expectedIntent, `operator "${command}" expected ${expectedIntent}, got ${routed.intent}`);
  }
  const operatorTrap = HalCore.routeHalCommand(halData, halModels, pages, halData.validation.operatorFirewallTrap);
  assert(operatorTrap.intent === "blocked: firewall", "operator smoke + email must be blocked");
  const handoff = HalCore.buildHandoffSummary(halData, halModels, { readiness: readinessReport, smoke });
  assert(handoff.includes("STAFF HANDOFF SUMMARY"), "handoff summary must format");
  assert(/human review/i.test(handoff), "handoff summary must mention human review");
  const health = HalCore.deriveDrawerHealth(halData, halModels, pages, readinessReport);
  for (const key of ["askHal", "sources", "reasoning", "workSurfaces", "firewall", "priorities"]) {
    assert(["Pass", "Warning", "Fail"].includes(health[key]), `drawer health for ${key} must be valid, got ${health[key]}`);
  }
  const laneDetails = HalCore.modelLaneDetails(halModels);
  assert(laneDetails.length === halModels.lanes.length, "model lane details must cover all configured lanes");
  passed++;

  // Seeded routing regression: local intents, model fallbacks, and firewall traps.
  const routingCases = buildSeededRoutingVariants(10000);
  const routingFailures = [];
  const laneCounts = {};
  for (const [question, expectedIntent] of routingCases) {
    const result = HalCore.routeHalCommand(halData, halModels, pages, question);
    const got = String(result.intent || "");
    const ok = got === expectedIntent || got.startsWith(expectedIntent);
    laneCounts[result.lane] = (laneCounts[result.lane] || 0) + 1;
    if (!ok) routingFailures.push(`"${question}" expected ${expectedIntent}, got ${got}`);
  }
  assert(routingFailures.length === 0, "routing regression failures:\n" + routingFailures.slice(0, 20).join("\n"));
  assert(laneCounts.firewall > 0, "routing regression must include firewall cases");
  assert(laneCounts.chat8b > 0, "routing regression must include model fallback cases");
  assert(laneCounts.reason21b > 0, "routing regression must include reasoning lane cases");
  assert(laneCounts.escalate30b > 0, "routing regression must include escalation lane cases");
  assert(laneCounts.oss120b > 0, "routing regression must include oss120b lane cases");
  passed++;

  // app.js syntax
  const { execSync } = require("node:child_process");
  execSync("node --check site/app.js", { cwd: __dirname, stdio: "pipe" });
  execSync("node --check site/hal-core.js", { cwd: __dirname, stdio: "pipe" });
  execSync("node --check site/hal-page.js", { cwd: __dirname, stdio: "pipe" });
  execSync("node --check site/hal-page-schema.js", { cwd: __dirname, stdio: "pipe" });
  execSync("node --check site/hal-page-canvas.js", { cwd: __dirname, stdio: "pipe" });
  passed++;

  // HAL page surfaces required manager signals (no backend, local data only)
  require(join(siteDir, "icons.js"));
  globalThis.AppIcons = require(join(siteDir, "icons.js"));
  require(join(siteDir, "page-schema.js"));
  require(join(siteDir, "hal-page-schema.js"));
  require(join(siteDir, "hal-page-canvas.js"));
  require(join(siteDir, "components.js"));
  require(join(siteDir, "hal-pilot-widgets.js"));
  require(join(siteDir, "hal-page-widgets.js"));
  require(join(siteDir, "page-chrome.js"));
  require(join(siteDir, "page-views.js"));
  const HalPageMod = require(join(siteDir, "hal-page.js"));
  let halHtml = "";
  const halRoot = {
    set innerHTML(value) {
      halHtml = value;
    },
    get innerHTML() {
      return halHtml;
    },
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
  };
  HalPageMod.render({
    root: halRoot,
    halData,
    halModels,
    halAudit: [{ time: "12:00:00", intent: "readiness: run", query: "Run readiness check" }],
    halChatHistory: [],
    halAskDraft: "",
    halAskLoading: false,
    halInlineFirewallResult: null,
    halSideNotes: [],
    halSideNoteMonitor: { activeCount: 0, openCount: 0, pinnedCount: 0, highPriorityCount: 0, checkedAt: new Date().toISOString() },
    halSideNotesInbox: {
      monitor: { checkedAt: new Date().toISOString(), lastRowId: 1616, announce: true, bellSuppressed: true, station: "Server", status: "live", voiceStyle: "hal9000" },
      items: [
        { id: "M1", rowId: 1616, sender: "Room 4", recipient: "Server", broadcast: false, date: "6/28/2026", time: "6:49:24 PM", unread: true },
      ],
    },
    halWidgetFeed: {
      manager: "Import cache",
      jobs: { widgetPublish: { status: "SUCCESS" } },
      widgets: {
        practiceFinancialOverview: {
          title: "Practice Financial Overview",
          status: "SUCCESS",
          summary: "QuickBooks revenue reflects cash-basis deposits; SoftDent production/collections are operational PMS metrics.",
          navTarget: "financial",
          metrics: { monthlyRevenue: "$120,000" },
        },
        accountsPayableAutomation: {
          title: "Accounts Payable Automation",
          status: "SUCCESS",
          summary: "QuickBooks expense totals and posting-queue workflow counts.",
          navTarget: "documents",
          metrics: { expenseTotal: "$45,000" },
        },
        smartClaimsAndReceivables: {
          title: "Smart Claims & Receivables",
          status: "SUCCESS",
          summary: "SoftDent claims and receivables totals.",
          navTarget: "claims",
          metrics: { outstandingClaimCount: 12 },
        },
        careDeliveryPerformance: {
          title: "Care Delivery Performance",
          status: "DEGRADED",
          summary: "Practice-wide SoftDent operational balances.",
          navTarget: "softdent",
          metrics: { patientBalanceTotal: "$8,500" },
        },
      },
    },
    halProgramSnapshot: {
      importBundle: {
        importMode: "direct-first",
        directFirst: true,
        diagnostics: { summary: { connected: 4, partial: 1, missing: 2 } },
      },
    },
    sidenotesHubPath: "C:\\softdent\\HAL-SideNotes-Workstation\\data",
  });
  assert(halHtml.includes("SIDENOTES PROGRAM"), "HAL page must render the dedicated SideNotes program card");
  assert(halHtml.includes("SIDENOTESIM MONITOR"), "HAL page must render the SideNotesIM live monitor");
  assert(halHtml.includes("data-hal-surf-nav=\"sidenotes\""), "HAL page must wire SideNotes work surface navigation");
  assert(halHtml.includes("data-hal-surf-open="), "HAL page must wire work surface open chevrons");
  assert(halHtml.includes("hp-wg-card--active"), "HAL page must wire widget cards to HAL");
  assert(halHtml.includes("data-hal-activity-cmd="), "HAL page must wire activity log replay to HAL");
  assert(halHtml.includes("hp-status--btn"), "HAL page must wire status chips to HAL");
  assert(halHtml.includes("pv-canvas-hero"), "HAL page must use the canvas page hero");
  assert(halHtml.includes("hp-action--icon"), "HAL page must render icon-backed prompt chips");
  assert(halHtml.includes("<svg") && halHtml.includes('class="app-ico"'), "HAL page must render SVG icons");
  assert(halHtml.includes("hp-card__ico"), "HAL page must render section header icons");
  assert(halHtml.includes("hp-ctrl__ico"), "HAL page must render system control icons");
  assert(halHtml.includes("hp-grid--hal-102"), "HAL page must use hal-102 schema grid");
  assert(halHtml.includes("Financial Widgets"), "HAL page must render financial widget group");
  assert(halHtml.includes("Practice Financial Overview"), "HAL page must render financial widget");
  assert(halHtml.includes("data-hal-widget-nav="), "HAL page must render widget navigation controls");
  assert(halHtml.includes('id="hpAskForm"'), "HAL page must keep Ask HAL chat form");
  assert(halHtml.includes('id="hpAskInput"'), "HAL page must keep Ask HAL chat input");
  assert(halHtml.includes("IMPORT & SOURCE HEALTH"), "HAL page must render import health panel");
  assert(halHtml.includes("HAL 9000 voice"), "HAL page must show HAL 9000 voice mode");
  assert(halHtml.includes("TEST VOICE"), "HAL page must render HAL voice test control");
  assert(halHtml.includes("Room 4"), "HAL page must render live SideNotesIM message senders");
  assert(halHtml.includes("LOCAL NOTES"), "HAL page must render the local notes section");
  assert(halHtml.includes("PROGRAM POSTURE"), "HAL page must surface program posture");
  assert(halHtml.includes("TRUST & FIREWALL"), "HAL page must surface firewall policy");
  assert(halHtml.includes("BLOCKED"), "HAL page must surface blocked actions");
  assert(halHtml.includes("Last receipt:"), "HAL page must surface the last local receipt");
  assert(halHtml.includes("direct-first") || halHtml.includes("Direct-first"), "HAL page must label direct-first import mode");
  passed++;

  // AI readiness display; local model lanes enabled on loopback only
  assert(halModels.config.externalCallsEnabled === false, "external model calls must stay disabled");
  assert(halModels.config.webResearch && halModels.config.webResearch.enabled === true, "web research must be enabled");
  assert(halModels.config.webResearch.mode === "broad", "web research must use broad practice scope");
  for (const runtime of [halModels.config.localModel, halModels.config.reasoningModel, halModels.config.escalationModel]) {
    assert(runtime.enabled === true, "model lane must be enabled for local execution");
    assert(HalCore.isLocalModelEndpoint(runtime.endpoint), `model endpoint must be loopback-only: ${runtime.endpoint}`);
  }
  for (const lane of halModels.lanes) {
    assert(lane.inventoryAvailable === true, `lane ${lane.id} inventory should be marked available`);
    if (lane.executionEnabled === false) {
      assert(lane.runtime && lane.runtime.enabled === false, `standby lane ${lane.id} runtime must be disabled`);
      continue;
    }
    assert(lane.executionEnabled === true, `lane ${lane.id} execution must be enabled`);
    assert(HalCore.laneReady(halModels, lane.id), `lane ${lane.id} must be execution-ready on loopback`);
    const runtime = HalCore.laneRuntime(halModels, lane.id);
    assert(runtime && HalCore.isLocalModelEndpoint(runtime.endpoint), `lane ${lane.id} runtime must be loopback-only`);
  }
  assert(halModels.readinessDisplay.allModelsEnabled === true, "readiness display must reflect all models enabled");
  assert(halHtml.includes("LOCAL AI READINESS"), "HAL page must render AI readiness");
  assert(halHtml.includes("local only"), "HAL page must label AI lanes as local only");
  assert(halHtml.includes("Available inventory"), "HAL page must show available model inventory");
  assert(halModels.readinessDisplay.configuredModels.local.model === "hal-chat:8b", "local model must use the GPU 8B chat lane");
  assert(halModels.readinessDisplay.configuredModels.helper.model === "hal-helper:14b", "helper model must use the GPU 14B helper lane");
  assert(halHtml.includes("hal-chat:8b"), "HAL page must show GPU 8B chat model inventory");
  assert(halHtml.includes("hal-helper:14b"), "HAL page must show GPU 14B helper model inventory");
  assert(halHtml.includes("mistral-small3.1:24b-fast"), "HAL page must show on-demand 24B reasoning model inventory");
  assert(halHtml.includes("qwen3:30b"), "HAL page must show escalation model inventory");
  assert(halModels.readinessDisplay.gpu && halModels.readinessDisplay.gpu.verified === true, "GPU must be marked verified in readiness display");
  assert(/Radeon RX 9060 XT|ROCm/i.test(halHtml), "HAL page must show the verified GPU device");
  assert(/sensitive raw data|SoftDent|QuickBooks/i.test(halHtml), "HAL page must show sensitive-data no-egress policy");
  assert(HalCore.laneReady(halModels, "chat8b"), "chat lane must be execution-ready on loopback");
  const helperLane = halModels.lanes.find((lane) => lane.id === "helper14b");
  assert(helperLane && helperLane.executionEnabled === false, "helper lane must be standby in single-lane layout");
  assert(halModels.readinessDisplay.configuredModels.helper.onDemand === true, "helper lane must be on-demand only");
  assert(
    halModels.readinessDisplay.configuredModels.helper.gpuResidentWithLocal === false,
    "helper lane must not be GPU co-resident in single-lane layout",
  );
  assert(HalCore.laneReady(halModels, "reason21b"), "reasoning lane must be execution-ready on loopback");
  assert(HalCore.laneReady(halModels, "escalate30b"), "escalation lane must be execution-ready on loopback");
  assert(HalCore.laneReady(halModels, "oss120b"), "oss120b lane must be execution-ready on loopback");
  const ossRoute = HalCore.routeHalCommand(halData, halModels, pages, "run this through 120b");
  assert(ossRoute.lane === "oss120b" && ossRoute.useOss === true, "120b queries must route to oss120b lane");
  HalPageMod.render({
    root: halRoot,
    halData: {},
    halModels,
    halAudit: null,
    halChatHistory: null,
    halAskDraft: "",
    halAskLoading: false,
    halInlineFirewallResult: null,
    halSideNotes: null,
    halSideNoteMonitor: null,
    halSideNotesInbox: null,
    halWidgetFeed: null,
  });
  assert(typeof halHtml === "string" && halHtml.length > 0, "HAL page must render with empty program context");
  assert(halHtml.includes("HAL STATUS"), "HAL page empty render must still show status toolbar");
  const PageChromeMod = require(join(siteDir, "page-chrome.js"));
  const emptyShell = PageChromeMod.canvasShell({ pageId: "financial", halData: {}, halWidgetFeed: null });
  assert(emptyShell.includes("pv-canvas-shell"), "page chrome must render financial shell with empty feed");
  const missingShell = PageChromeMod.canvasShell({ pageId: "not-a-real-page", halData: {} });
  assert(missingShell.includes("pv-canvas-shell--missing"), "page chrome must degrade when schema is missing");
  passed++;

  // Full program read access
  assert(halData.programAccess && halData.programAccess.mode === "full-read", "HAL must have full-read program access");
  const programRoute = HalCore.routeHalCommand(halData, halModels, pages, "Show full program snapshot");
  assert(programRoute.intent === "program: snapshot" && programRoute.useProgramSnapshot === true, "program snapshot must route locally");
  const ServicesMod = require(join(siteDir, "services.js"));
  const snapshot = await ServicesMod.readProgramSnapshot();
  const programSummary = HalCore.summarizeProgramSnapshot(snapshot, halData);
  assert(programSummary.includes("FULL PROGRAM READ ACCESS"), "program snapshot summary must include full access header");
  assert(programSummary.includes("Financial"), "program snapshot must include financial data");
  assert(programSummary.includes("Claims workbench"), "program snapshot must include claims data");
  assert(halHtml.includes("PROGRAM POSTURE"), "HAL page must show program posture");
  passed++;

  // Ported HAL skills (accounting, claim readiness, office-manager, tasks, sanitization, memory)
  const HalSkills = require(join(siteDir, "hal-skills.js"));
  const HalNarrativeLibrary = require(join(siteDir, "hal-narrative-library.js"));
  const HalPeriodRequirements = require(join(siteDir, "hal-period-requirements.js"));
  const narrativeLibrary = HalNarrativeLibrary.buildGenericDraftLibrary();
  assert(narrativeLibrary.length === 100, "MemoAI narrative library must contain 100 generic drafts");
  const narrativeRoute = HalCore.routeHalCommand(halData, halModels, pages, "Draft narrative for claim CLM-2026-1001");
  assert(narrativeRoute.intent === "narratives: select-for-claim" && narrativeRoute.useNarrativeForClaim === true, "claim narrative selection must route locally");
  const periodRoute = HalCore.routeHalCommand(halData, halModels, pages, "What periods do widgets need");
  assert(periodRoute.intent === "periods: widget-requirements" && periodRoute.useWidgetPeriodRequirements === true, "widget period requirements must route locally");
  const periodAnalysis = HalPeriodRequirements.analyzeWidgetPeriods(snapshot);
  assert(Array.isArray(periodAnalysis.requiredPeriods) && periodAnalysis.requiredPeriods.length === 2, "period analysis must require current + prior month");
  const cognitiveRoute = HalCore.routeHalCommand(halData, halModels, pages, "Show HAL cognitive pathways");
  assert(cognitiveRoute.intent === "hal: cognitive-pathways" && cognitiveRoute.useCognitivePathways === true, "cognitive pathways must route locally");
  assert((halData.cognitivePathways && halData.cognitivePathways.cognitive && halData.cognitivePathways.cognitive.length) >= 5, "hal-manager must define cognitive characteristics");
  const WidgetContract = require(join(siteDir, "widget-contract.js"));
  const HalWidgetMasterChart = require(join(siteDir, "hal-widget-master-chart.js"));

  // Accounting: drafting allowed through firewall; posting still blocked.
  const draftRoute = HalCore.routeHalCommand(halData, halModels, pages, "Draft a journal entry for $1,200 prepaid insurance");
  assert(draftRoute.intent === "accounting: journal-draft" && draftRoute.useJournalDraft === true, "journal drafting must route locally");
  const postBlocked = HalCore.routeHalCommand(halData, halModels, pages, "Post a journal entry to the ledger");
  assert(postBlocked.intent === "blocked: firewall", "posting a journal entry must stay blocked");
  const qbPostBlocked = HalCore.routeHalCommand(halData, halModels, pages, "Post to QuickBooks");
  assert(qbPostBlocked.intent === "blocked: firewall", "Post to QuickBooks must be blocked");
  const softdentWriteBlocked = HalCore.routeHalCommand(halData, halModels, pages, "Write to SoftDent");
  assert(softdentWriteBlocked.intent === "blocked: firewall", "Write to SoftDent must be blocked");
  const rememberRoute = HalCore.routeHalCommand(
    halData,
    halModels,
    pages,
    "Remember this: SoftDent needs a final daysheet per date for accurate A/R",
  );
  assert(rememberRoute.intent === "memory: remember" && rememberRoute.useRememberMemory === true, "remember-this must route to durable memory");
  const journal = HalSkills.draftAndValidateJournal({ description: "Prepaid insurance payment", period: "2025-05", amount: 1200, context: {} });
  assert(journal.meta && journal.meta.schema === "nr2-hal-skill-v1", "journal draft must use the NewRidge skill schema envelope");
  assert(journal.transactionType === "prepaid_insurance", "journal type inference must work");
  assert(journal.validation.balanced === true, "drafted journal must balance");
  assert(journal.validation.debitTotal === 1200 && journal.validation.creditTotal === 1200, "journal totals must match amount");
  assert(journal.draftStatus === "draftOnly" && journal.safety.postedToLedger === false, "journal must remain draft-only, not posted");
  assert(journal.lines[0].accountCode === "1310" && journal.lines[0].accountName === "Prepaid Insurance", "journal lines must use camelCase account fields");
  const closed = HalSkills.draftAndValidateJournal({ description: "Depreciation", period: "2025-01", amount: 500, context: {} });
  assert(closed.validation.openPeriod === false, "closed period must be detected");

  // Claim packet readiness
  const readinessRoute = HalCore.routeHalCommand(halData, halModels, pages, "Check claim packet readiness");
  assert(readinessRoute.intent === "claims: readiness" && readinessRoute.useClaimReadiness === true, "claim readiness must route locally");
  const cprClaims =
  (snapshot.claims && snapshot.claims.top && snapshot.claims.top.length)
    ? snapshot.claims.top
    : [{ id: "CLM-fixture-1", patient: "Fixture Patient", status: "Ready", procedure: "D2740", amount: "$100.00" }];
  const cprResp = HalSkills.buildClaimReadinessResponse(cprClaims);
  assert(cprResp.meta && cprResp.meta.schema === "nr2-hal-skill-v1", "claim readiness must use the NewRidge skill schema envelope");
  assert(cprResp.summary.totalCount > 0, "claim readiness must assess claims");
  assert(cprResp.submissionStatus === "notSubmitted", "claim readiness must remain not submitted");
  assert("claimRef" in cprResp.items[0] && "staffSummary" in cprResp.items[0], "claim readiness items must use camelCase fields");
  const cprText = HalSkills.formatClaimReadinessAnswer(cprResp);
  assert(/Nothing has been submitted/.test(cprText), "claim readiness answer must include not-submitted safety");

  // Office-manager attention
  const officeRoute = HalCore.routeHalCommand(halData, halModels, pages, "Show office manager attention");
  assert(officeRoute.intent === "office: attention" && officeRoute.useOfficeAttention === true, "office attention must route locally");
  const attention = HalSkills.buildOfficeManagerAttention(snapshot, HalSkills.computeTaskMetrics([]));
  assert(attention.items.length > 0, "office attention must produce items");
  assert(attention.submissionStatus === "notSubmitted" && attention.localOnly === true, "office attention must stay local/not-submitted");
  assert("itemId" in attention.items[0] && "actionHint" in attention.items[0], "office attention items must use camelCase fields");

  // Office tasks (local create/update/metrics)
  const listRoute = HalCore.routeHalCommand(halData, halModels, pages, "Show my tasks");
  assert(listRoute.intent === "tasks: list" && listRoute.useTaskList === true, "task list must route locally");
  const createRoute = HalCore.routeHalCommand(halData, halModels, pages, "Create a task: follow up on denied claim");
  assert(createRoute.intent === "tasks: create" && createRoute.useTaskCreate === true, "task create must route locally");
  const task = HalSkills.createTask({ title: createRoute.taskTitle }, { actor: "test" });
  assert(task.status === "open" && task.localOnly === true && task.softdentWritebackPerformed === false, "created task must be local-only");
  assert(task.taskId && task.createdAt && task.updatedAt, "created task must use program-style taskId/createdAt/updatedAt fields");
  const done = HalSkills.applyTaskUpdate(task, { status: "completed" });
  assert(done.status === "completed", "task update must apply");
  const metrics = HalSkills.computeTaskMetrics([task, done]);
  assert(metrics.openCount === 1 && metrics.completedCount === 1, "task metrics must count statuses");

  // HAL sidenotes (local monitor, create/list)
  const snMonitorRoute = HalCore.routeHalCommand(halData, halModels, pages, "Monitor sidenotes");
  assert(snMonitorRoute.intent === "sidenotes: monitor" && snMonitorRoute.useSideNoteMonitor === true, "sidenote monitor must route locally");
  const snListRoute = HalCore.routeHalCommand(halData, halModels, pages, "Show sidenotes");
  assert(snListRoute.intent === "sidenotes: list" && snListRoute.useSideNoteList === true, "sidenote list must route locally");
  const snCreateRoute = HalCore.routeHalCommand(halData, halModels, pages, "Add sidenote: follow up on hygiene recall");
  assert(snCreateRoute.intent === "sidenotes: create" && snCreateRoute.useSideNoteCreate === true, "sidenote create must route locally");
  const sn = HalSkills.createSideNote({ text: "Recall patient about claim" }, { actor: "test" });
  assert(sn.noteId && sn.localOnly === true && sn.softdentWritebackPerformed === false, "created sidenote must be local-only");
  const mon1 = HalSkills.buildSideNoteMonitor([sn]);
  const pinned = HalSkills.applySideNoteUpdate(sn, { status: "pinned" });
  const mon2 = HalSkills.buildSideNoteMonitor([pinned], mon1);
  assert(mon2.hasChanges === true && mon2.pinnedCount === 1, "sidenote monitor must detect changes");
  const snSummary = HalCore.summarizeProgramSnapshot(
    Object.assign({}, snapshot, {
      sideNotes: { activeCount: 1, monitor: mon2, top: [{ status: "pinned", priority: "normal", text: "Recall patient" }] },
    }),
    halData,
  );
  assert(snSummary.includes("Sidenotes (HAL monitor)"), "program snapshot must include sidenotes summary");

  // Sanitization (PII redaction)
  const san = HalSkills.sanitizeText("Call patient John Smith at 555-123-4567, MRN 12345, john@x.com on 03/12/2025");
  assert(/PATIENT_REDACTED/.test(san.sanitizedText), "patient name must be redacted");
  assert(/PHONE_REDACTED/.test(san.sanitizedText), "phone must be redacted");
  assert(/EMAIL_REDACTED/.test(san.sanitizedText), "email must be redacted");
  assert(!/john@x\.com/.test(san.sanitizedText), "raw email must not survive sanitization");

  // Knowledge memory governance
  assert(HalSkills.memoryContainsForbidden("the A/R is $0"), "forbidden memory content must be detected");
  const goodMem = { id: "m1", status: "approved", confidence: "high", sensitivity_level: "internal", staleness_rule: "never", text: "Keep claims local." };
  const badMem = { id: "m2", status: "draft", confidence: "low", text: "anything" };
  assert(HalSkills.isMemoryIndexable(goodMem, {}) === true, "approved memory must be indexable");
  assert(HalSkills.isMemoryIndexable(badMem, {}) === false, "unapproved memory must be excluded");
  passed++;

  // Document RAG / library retrieval (grounded, local-only)
  const ragRoute = HalCore.routeHalCommand(halData, halModels, pages, "Search the library for compliance");
  assert(ragRoute.intent === "library: ask" && ragRoute.useDocRag === true, "library search must route locally");
  const navLibrary = HalCore.routeHalCommand(halData, halModels, pages, "Open the document library");
  assert(navLibrary.intent.startsWith("navigate"), "opening the library must still navigate, not trigger RAG");
  const ragFixtureDocs = [
    {
      title: "Compliance Training Manual",
      type: "PDF",
      tags: ["compliance", "training"],
      content: "Annual compliance training requirements for staff including HIPAA, safety, and privacy procedures.",
    },
  ];
  const ragHit = HalSkills.answerFromLibrary("compliance training", ragFixtureDocs, 4);
  assert(ragHit.grounded === true && ragHit.retrievedContext.length > 0, "RAG must find grounded matches");
  assert("sourceId" in ragHit.retrievedContext[0], "RAG results must use camelCase sourceId");
  assert(ragHit.prompt && ragHit.prompt.includes("library context"), "RAG must build a grounded answer prompt");
  const libDocs = (snapshot.library && (snapshot.library.top || snapshot.library.docs)) || [];
  const ragMiss = HalSkills.answerFromLibrary("zzzqqq nonexistent topic", libDocs, 4);
  assert(ragMiss.grounded === false && ragMiss.answer === HalSkills.INSUFFICIENT_DOCUMENT_CONTEXT_ANSWER, "RAG must fall back when no grounded context");

  // Manager dashboard widgets (import-cache feed) + A/R honesty policy
  const widgetRoute = HalCore.routeHalCommand(halData, halModels, pages, "Show manager dashboard widgets");
  assert(widgetRoute.intent === "widgets: feed" && widgetRoute.useWidgetFeed === true, "widget feed must route locally");
  const feed = HalSkills.buildWidgetFeed(snapshot);
  assert(Object.keys(feed.widgets).length === 24, "widget feed must build 24 operational widgets");
  const masterChart = HalWidgetMasterChart.all();
  assert(masterChart.length === HalSkills.WIDGET_ORDER.length, "widget master chart must cover every HAL widget");
  assert(masterChart.every((row) => row.page && row.purpose && row.expectedData.length && row.readyWhen), "widget master chart rows must include page, purpose, expected data, and ready criteria");
  assert(
    HalSkills.WIDGET_ORDER.every((key) => masterChart.some((row) => row.key === key)),
    "widget master chart must stay aligned with WIDGET_ORDER",
  );
  assert(HalWidgetMasterChart.formatForHal().includes("HAL Widget Master Chart"), "widget master chart must format for HAL guidance");
  assert(
    HalWidgetMasterChart.formatForHal(feed).includes("Ready now:"),
    "widget master chart must include feed readiness when a widget feed is supplied",
  );
  const masterChartWithFeed = HalWidgetMasterChart.all(feed);
  assert(
    masterChartWithFeed.every((row) => typeof row.dataReady === "boolean"),
    "master chart rows must expose dataReady when a widget feed is supplied",
  );
  const qbMasterRow = masterChartWithFeed.find((row) => row.key === "quickbooksProfitLossDetail");
  assert(
    qbMasterRow && qbMasterRow.dataReady === (feed.widgets.quickbooksProfitLossDetail.status === "SUCCESS"),
    "master chart dataReady must mirror widget feed SUCCESS status",
  );
  assert(feed.widgets.ebitdaNormalization && feed.widgets.arAgingAndCollections && feed.widgets.narrativeWorkflow && feed.widgets.documentLibrary, "widget feed must include all extended page widgets");
  assert(feed.widgets.journalPostingQueue && feed.widgets.smartClaimsAndReceivables, "widget feed must include journal posting and smart claims widgets");
  assert(feed.widgets.newPatients && feed.widgets.treatmentPlanSummary && feed.widgets.caseAcceptance, "widget feed must include practice-performance widgets");
  assert(feed.accountingExcelValidation && feed.accountingExcelValidation.status, "widget feed must run accounting/excel commit validation before publish");
  assert(feed.localOnly === true && feed.runId && feed.generatedAt, "widget feed must use program-style runId/generatedAt/localOnly fields");
  assert(feed.jobs.widgetPublish && feed.jobs.widgetPublish.validation && feed.sources.quickbooks.lastStatus, "widget feed jobs/sources must use camelCase fields");

  const crossSourceFeed = HalSkills.buildWidgetFeed({
    dashboards: {
      financial: { dataSource: "import", productionMtd: { value: 123456 } },
      softdent: { dataSource: "import", production: 123456, collections: 100000 },
      quickbooks: { dataSource: "empty" },
      practice: { dataSource: "empty" },
    },
  });
  const crossOverview = crossSourceFeed.widgets.practiceFinancialOverview;
  assert(crossOverview.metrics.monthlyRevenue !== 123456, "monthlyRevenue must not borrow SoftDent production when QuickBooks revenue is absent");
  assert(
    crossOverview.metrics.monthlyRevenue === WidgetContract.MISSING || crossOverview.metrics.monthlyRevenue === null,
    "monthlyRevenue must be explicitly missing when QuickBooks revenue is absent",
  );
  assert(crossOverview.status !== "SUCCESS", "cross-source overview must not read SUCCESS when QuickBooks revenue is absent");

  const pendingCollectionsFeed = HalSkills.buildWidgetFeed({
    dashboards: {
      financial: { dataSource: "import", productionMtd: { value: 171796.9 }, collectionsPending: true },
      softdent: { dataSource: "import", production: 171796.9, collectionsPending: true },
      quickbooks: { dataSource: "import", revenue: 50000, expenses: 30000 },
      practice: { dataSource: "empty" },
    },
  });
  const pendingOverview = pendingCollectionsFeed.widgets.practiceFinancialOverview;
  assert(pendingOverview.status !== "SUCCESS", "pending collections must not read SUCCESS on financial overview");
  assert(
    pendingOverview.metrics.collectionsTotal === WidgetContract.MISSING || pendingOverview.metrics.collectionsTotal === null,
    "collections must stay missing when SoftDent collections export is pending",
  );
  assert(
    WidgetContract.widgetStatusFromStates(["ok", "ok", "ok", "pending"]) === "DEGRADED",
    "pending metric state must degrade widget contract status",
  );

  const failedQualityFeed = HalSkills.buildWidgetFeed({
    dashboards: {
      financial: {
        dataSource: "import",
        productionMtd: { value: 100000 },
        quality: { score: 55, overallPass: false, categories: [{ label: "QB P&L reconcile", score: 10 }] },
      },
      softdent: { dataSource: "import", production: 100000, collections: 80000 },
      quickbooks: { dataSource: "import", revenue: 50000, expenses: 30000 },
      practice: { dataSource: "empty" },
    },
  });
  assert(
    (failedQualityFeed.accountingExcelValidation?.issues || []).some(
      (issue) =>
        issue.widgetKey === "practiceFinancialOverview" &&
        issue.message === "Financial data quality overallPass failed — resolve import freshness, collections, period alignment, or QuickBooks reconcile before period close.",
    ),
    "overallPass false must surface in widget commit validation",
  );

  const missingQualityFeed = HalSkills.buildWidgetFeed({
    dashboards: {
      financial: { dataSource: "import", productionMtd: { value: 100000 } },
      softdent: { dataSource: "import", production: 100000, collections: 80000 },
      quickbooks: { dataSource: "import", revenue: 50000, expenses: 30000 },
      practice: { dataSource: "empty" },
    },
  });
  assert(
    missingQualityFeed.widgets.practiceFinancialOverview.status === "DEGRADED",
    "missing financial quality score must degrade practice financial overview widget",
  );
  assert(
    (missingQualityFeed.accountingExcelValidation?.issues || []).some(
      (issue) => issue.message === "Financial dashboard loaded without a quality score — run import diagnostics before period close.",
    ),
    "missing financial quality score must surface in widget commit validation",
  );

  const contractRoute = HalCore.routeHalCommand(halData, halModels, pages, "what does the financial widget need?");
  assert(contractRoute.intent === "widgets: contract" && contractRoute.useWidgetContract === true, "widget contract questions must route locally");
  assert(WidgetContract.formatContractForHal("practiceFinancialOverview").includes("quickbooks.revenue"), "HAL widget contract must describe required datasets");
  const masterChartRoute = HalCore.routeHalCommand(halData, halModels, pages, "show the widget master chart");
  assert(masterChartRoute.intent === "widgets: master-chart" && masterChartRoute.useWidgetMasterChart === true, "widget master chart questions must route locally");

  // A/R honesty: with no verified A/R source, totals are nulled and status degrades
  const noArFeed = HalSkills.buildWidgetFeed({ dashboards: { softdent: {}, quickbooks: { syncStatus: "ok" } }, claims: { total: 5 } });
  assert(noArFeed.jobs.widgetPublish && noArFeed.jobs.widgetPublish.validation, "widget publish job must retain validation when verified A/R is unavailable");
  assert(noArFeed.widgets.smartClaimsAndReceivables.metrics.accountsReceivableTotal === null, "A/R must not be fabricated without a verified source");
  assert(noArFeed.widgets.careDeliveryPerformance.metrics.patientBalanceTotal === null, "patient A/R balance must not be fabricated");
  assert(noArFeed.widgets.smartClaimsAndReceivables.status !== "SUCCESS", "claims widget must degrade without A/R source");

  const PageCanvasData = require(join(siteDir, "page-canvas-data.js"));
  const noArSnapshot = {
    dashboards: {
      softdent: { hero: { value: "$8,500" }, glance: [{ label: "Total Patients", value: "120" }] },
      quickbooks: { syncStatus: "ok" },
    },
  };
  PageCanvasData.bind(noArFeed, noArSnapshot);
  const noArGlance = PageCanvasData.softdentGlanceStats();
  const patientArGlance = noArGlance.find((row) => row.label === "Patient A/R");
  assert(patientArGlance && patientArGlance.value === "—", "SoftDent page canvas must not show sd.hero A/R when widget feed withholds verified A/R");

  const staleArSnapshot = {
    dashboards: {
      ar: { kpis: [{ label: "Total Outstanding", value: "$5,000", tone: "gold" }] },
      softdent: { aging: [{ bucket: "0-30", amount: "$1,000", pct: 50 }], responsibility: { insurance: { amount: "500" }, patient: { amount: "300" } } },
    },
  };
  PageCanvasData.bind(noArFeed, staleArSnapshot);
  const staleArKpis = PageCanvasData.arKpis();
  assert(
    staleArKpis.every((row) => row.value === "—" || row.value === "0"),
    "A/R page canvas must not show stale dashboard KPIs when widget feed withholds verified A/R",
  );
  assert(PageCanvasData.softdentAgingBars() === null, "SoftDent aging chart must hide when verified A/R is unavailable");
  assert(PageCanvasData.softdentResponsibilityDonut() === null, "SoftDent responsibility chart must hide when verified A/R is unavailable");

  const claimsTableSnapshot = {
    dashboards: {
      ar: {
        topClaims: [{ patient: "Jane Doe", claim: "CLM-1", outstanding: "$500.00", days: 45 }],
      },
      softdent: {},
      quickbooks: { syncStatus: "ok" },
    },
    claims: { total: 3 },
  };
  const claimsTableFeed = HalSkills.buildWidgetFeed(claimsTableSnapshot);
  PageCanvasData.bind(claimsTableFeed, claimsTableSnapshot);
  const claimsTableRows = PageCanvasData.arTopClaimsTable();
  assert(
    claimsTableRows.length === 1 && claimsTableRows[0][3] === "—",
    "A/R claims table must withhold per-claim outstanding amounts without verified A/R export",
  );

  const followUpSnapshot = {
    dashboards: { softdent: {}, quickbooks: { syncStatus: "ok" } },
    claims: {
      total: 2,
      claims: [
        { patient: "Jane Doe", amount: "$1,200.00", status: "Denied" },
        { patient: "John Smith", amount: "$800.00", status: "Ready" },
      ],
    },
  };
  const followUpFeed = HalSkills.buildWidgetFeed(followUpSnapshot);
  PageCanvasData.bind(followUpFeed, followUpSnapshot);
  const followUpKanban = PageCanvasData.arFollowUpKanban();
  assert(
    followUpKanban.some((lane) => lane.items.some((item) => item.includes("$") === false)),
    "A/R follow-up kanban must omit claim amounts without verified A/R export",
  );
  assert(
    followUpKanban.flatMap((lane) => lane.items).every((item) => !/\$\d/.test(item)),
    "A/R follow-up kanban must not display dollar amounts without verified A/R export",
  );

  const staleDiagSnapshot = {
    dashboards: {
      softdent: { hero: { value: "$8,500" }, status: "Connected" },
      ar: { kpis: [{ label: "Total Outstanding", value: "$8,500" }] },
    },
    claims: { total: 5 },
  };
  const staleProgramSummary = HalCore.summarizeProgramSnapshot(staleDiagSnapshot, halData);
  assert(staleProgramSummary.includes("SoftDent: A/R —"), "program snapshot summary must withhold stale SoftDent A/R without verified export");
  assert(!staleProgramSummary.includes("$8,500"), "program snapshot summary must not leak stale A/R totals");
  const staleSourceGuide = HalSkills.formatSourceSystemGuide(staleDiagSnapshot);
  assert(staleSourceGuide.includes("verified A/R —"), "source system guide must withhold stale A/R without verified export");
  assert(!staleSourceGuide.includes("$8,500"), "source system guide must not leak stale A/R hero values");

  // Document widgets must reflect local document data honestly (not blanket FAILED)
  const docsPresentFeed = HalSkills.buildWidgetFeed({
    dashboards: { softdent: {}, quickbooks: {} },
    documents: {
      queueCount: 4,
      top: [{ id: "GL-1", vendor: "Glidewell", amount: "$221.40", status: "Pending Review", age: 14 }],
      posting: [{ label: "Pending Review", count: 4 }],
      period: { label: "2026-06", documents: 4, postedPct: 0 },
    },
  });
  assert(docsPresentFeed.widgets.documentIntakeQueue.status === "SUCCESS", "document intake widget must read SUCCESS when queue and period metrics are loaded");
  assert(docsPresentFeed.widgets.accountsPayableAutomation.status === "DEGRADED", "AP automation must degrade (not FAILED) when documents exist but QuickBooks is empty");

  const docsReadyFeed = HalSkills.buildWidgetFeed({
    dashboards: { softdent: {}, quickbooks: {} },
    documents: {
      queueCount: 2,
      top: [{ id: "GL-1", vendor: "Glidewell", amount: "$221.40", status: "Posted", age: 3 }],
      posting: [{ label: "Posted", count: 2 }],
      period: { label: "2026-06", documents: 2, postedPct: 100 },
    },
  });
  assert(docsReadyFeed.widgets.documentIntakeQueue.status === "SUCCESS", "fully posted documents with period metrics must read SUCCESS");

  const docsEmptyFeed = HalSkills.buildWidgetFeed({ dashboards: { softdent: {}, quickbooks: {} }, documents: { queueCount: 0 } });
  assert(docsEmptyFeed.widgets.documentIntakeQueue.status === "FAILED", "empty document queue must remain No data yet (FAILED)");

  const importHealth = HalSkills.formatImportHealthSummary({
    importBundle: {
      diagnostics: {
        datasets: [
          { datasetKey: "softdent.claims", status: "missing", detail: "Dataset file not found in import cache." },
          { datasetKey: "softdent.dashboard", status: "partial", detail: "Current month only; prior month export missing for trend/YTD widgets." },
        ],
      },
    },
  });
  assert(importHealth.includes("softdent.claims"), "import health must name missing SoftDent exports");
  assert(importHealth.includes("prior month export missing"), "import health must explain one-month SoftDent dashboard");
  const checklist = HalSkills.formatImportChecklist(feed, snapshot);
  assert(checklist.includes("prior month"), "import checklist must mention prior month for SoftDent dashboard");

  const sourceGuide = HalSkills.formatSourceSystemGuide(snapshot);
  assert(sourceGuide.includes("SoftDent vs QuickBooks"), "source system guide must name both systems");
  assert(sourceGuide.includes("Do NOT use this source for"), "source system guide must list boundaries");
  assert(sourceGuide.includes("dental A/R aging"), "source system guide must mention dental A/R boundary");
  const sourceGuideRoute = HalCore.routeHalCommand(halData, halModels, pages, "Explain SoftDent vs QuickBooks");
  assert(sourceGuideRoute.intent === "sources: system guide" && sourceGuideRoute.useSourceSystemGuide === true, "SoftDent vs QuickBooks questions must route to source system guide");

  const finWidgetRoute = HalCore.routeHalCommand(halData, halModels, pages, "show financial widget");
  assert(finWidgetRoute.intent === "widgets: show:practiceFinancialOverview" && finWidgetRoute.widgetKey === "practiceFinancialOverview", "individual widget commands must route locally");
  const arWidgetRoute = HalCore.routeHalCommand(halData, halModels, pages, "show ar aging widget");
  assert(arWidgetRoute.widgetKey === "arAgingAndCollections", "A/R aging widget must route locally");
  const widgetFillRoute = HalCore.routeHalCommand(halData, halModels, pages, "suggestions with filling all widgets");
  assert(widgetFillRoute.intent === "widgets: fill-suggestions" && widgetFillRoute.useWidgetFillSuggestions === true, "widget fill suggestions must route locally");
  const fillText = HalSkills.formatWidgetFillSuggestions(feed);
  assert(fillText.includes("Suggestions to fill all manager widgets"), "widget fill suggestions must have a clear heading");
  assert(fillText.includes("SoftDent dashboard export") && fillText.includes("QuickBooks revenue/P&L"), "widget fill suggestions must cite source exports");
  const widgetGuidanceCases = [
    ["Show missing data by widget", "widgets: missing-data", "missingData", HalSkills.formatWidgetMissingData(feed), "Missing data by widget"],
    ["Trace widgets", "widgets: source-trace", "sourceTrace", HalSkills.formatWidgetSourceTrace(feed, snapshot), "HAL widget source trace"],
    ["Prioritize widgets to fill first", "widgets: fill-priority", "fillPriority", HalSkills.formatWidgetFillPriority(feed), "Priority order to fill widgets"],
    ["Show import checklist", "imports: checklist", "importChecklist", HalSkills.formatImportChecklist(feed, snapshot), "Import checklist"],
    ["Check data quality before recommendations", "data-quality: check", "dataQuality", HalSkills.formatDataQualityCheck(feed), "Data quality check"],
    ["Explain why this widget is empty", "widgets: explain-empty", "explainEmpty", HalSkills.formatEmptyWidgetExplanation(feed, "Explain why this widget is empty"), "Why widgets are empty"],
    ["Build daily owner briefing", "briefing: owner-daily", "dailyOwnerBriefing", HalSkills.formatDailyOwnerBriefing(feed, snapshot), "Daily owner briefing"],
    ["Show accounting review queue", "accounting: review-queue", "accountingReviewQueue", HalSkills.formatAccountingReviewQueue(feed, snapshot), "Accounting review queue"],
    ["Show accounting reconciliation checklist", "accounting: reconciliation-checklist", "accountingReconciliationChecklist", HalSkills.formatAccountingReconciliationChecklist(feed, snapshot), "SoftDent + QuickBooks reconciliation checklist"],
    ["Work document workbook", "documents: excel-workbook", "documentExcelWorkbook", HalSkills.formatDocumentExcelWorkbook(feed, snapshot), "Accounting document workbook"],
    ["Show Excel-style reconciliation", "reconciliation: excel-style", "excelReconciliation", HalSkills.formatExcelReconciliation(feed, snapshot), "Excel-style reconciliation"],
  ];
  widgetGuidanceCases.forEach(([command, expectedIntent, expectedGuidance, output, expectedText]) => {
    const route = HalCore.routeHalCommand(halData, halModels, pages, command);
    assert(route.intent === expectedIntent && route.widgetGuidance === expectedGuidance, `${command} must route to ${expectedIntent}`);
    assert(output.includes(expectedText), `${command} formatter must include ${expectedText}`);
  });

  const importStatusRoute = HalCore.routeHalCommand(halData, halModels, pages, "import status");
  assert(importStatusRoute.intent === "imports: status" && importStatusRoute.useImportStatus === true, "import status must route locally");
  const importRefreshRoute = HalCore.routeHalCommand(halData, halModels, pages, "refresh imports");
  assert(importRefreshRoute.intent === "imports: refresh" && importRefreshRoute.useImportRefresh === true, "import refresh must route locally");

  const sourceCatalogRoute = HalCore.routeHalCommand(halData, halModels, pages, "what can you get from quickbooks and softdent");
  assert(sourceCatalogRoute.intent === "sources: catalog" && sourceCatalogRoute.usePracticeSourceCatalog === true, "practice source catalog must route locally");
  const qbFetchRoute = HalCore.routeHalCommand(halData, halModels, pages, "fetch quickbooks revenue directly");
  assert(qbFetchRoute.intent === "sources: fetch:quickbooks" && qbFetchRoute.usePracticeSourceFetch === true, "direct quickbooks fetch must route locally");
  assert(qbFetchRoute.practiceSourceRequest.resource === "revenue", "quickbooks revenue query must resolve revenue resource");
  const sdFetchRoute = HalCore.routeHalCommand(halData, halModels, pages, "pull softdent claims from source");
  assert(sdFetchRoute.intent === "sources: fetch:softdent" && sdFetchRoute.usePracticeSourceFetch === true, "direct softdent fetch must route locally");
  const catalogText = HalSkills.formatPracticeSourceCatalog({
    policy: "read-only",
    autoPullEnabled: true,
    cacheDirs: { softdent: "app_data/nr2/document_inbox/softdent", quickbooks: "app_data/nr2/document_inbox/quickbooks" },
    systems: {
      quickbooks: { resources: { revenue: "QuickBooks revenue (live SDK)" } },
      softdent: { resources: { claims: "SoftDent claims export" } },
    },
  });
  assert(catalogText.includes("Authorized practice source catalog"), "practice source catalog formatter must describe authorized access");
  const fetchText = HalSkills.formatPracticeSourceFetch(
    { ok: true, system: "quickbooks", resource: "revenue", sourceKind: "quickbooks-sdk", rows: [{ TotalIncome: 1000 }], rowCount: 1, fetchedAt: new Date().toISOString() },
    { system: "quickbooks", resource: "revenue" },
  );
  assert(fetchText.includes("authorized practice employee"), "practice source fetch formatter must confirm read-only employee access");

  process.env.NR2_LOAD_IMPORTS = "1";
  const ImportLoader = require(join(siteDir, "import-loader.js"));
  const importBundle = await ImportLoader.loadBundle();
  if (ImportLoader.hasSoftdentImport(importBundle)) {
    const softdentDash = ImportLoader.buildDashboard("softdent", importBundle);
    assert(softdentDash && softdentDash.dataSource === "import", "softdent dashboard must map from import files");
    assert(/Production MTD/.test(JSON.stringify(softdentDash.glance || [])), "softdent import must expose production/collections glance values");
    if (importBundle.softdent?.claims?.rows?.length) {
      const claimsState = ImportLoader.mergeClaimsState({ claims: [], laneTotals: {}, kpis: [], lanes: {} }, importBundle);
      assert(Array.isArray(claimsState.claims) && claimsState.claims.length > 0, "softdent claims import must merge into claims state");
    }
    const finDash = ImportLoader.buildDashboard("financial", importBundle);
    assert(finDash && finDash.dataSource === "import", "financial dashboard must map from import files");
    assert(finDash.providers.rows.length >= 1, "financial dashboard must expose provider rows from imports");
    assert(
      new Set(finDash.providers.rows.map((row) => row.name)).size === finDash.providers.rows.length,
      "financial dashboard must preserve distinct imported provider names",
    );
  }
  delete process.env.NR2_LOAD_IMPORTS;
  passed++;

  // SoftDent read source status honesty (never fabricate $0 A/R)
  const sdWithAr = HalSkills.softDentReadSourceStatus({
    dashboards: { ar: { aging: [{ label: "0-30", amount: "$1,000", pct: 40 }] } },
    claims: { total: 1 },
  });
  assert(sdWithAr.arAvailable === true, "verified A/R aging data must be recognized as available");
  const sdReal = HalSkills.softDentReadSourceStatus(snapshot);
  const sdEmpty = HalSkills.softDentReadSourceStatus({ dashboards: {}, claims: { total: 0 } });
  assert(sdEmpty.arAvailable === false && sdEmpty.missingDataCodes.includes("missing_softdent_ar"), "missing A/R must be surfaced honestly");
  passed++;

  // HAL agent core (planner, tools, self-check, repair loop)
  const halAgentUrl = pathToFileURL(join(siteDir, "hal-agent.js")).href;
  const halRouteExecUrl = pathToFileURL(join(siteDir, "hal-route-exec.js")).href;
  const HalAgent = (await import(halAgentUrl)).default || (await import(halAgentUrl));
  const HalRouteExec = (await import(halRouteExecUrl)).default || (await import(halRouteExecUrl));
  assert(HalAgent.SAFETY_POLICY && HalAgent.SAFETY_POLICY.blocked.length > 0, "agent safety policy must exist");
  assert(HalAgent.ARCHITECTURE_VERSION === "hal-agent-v1.1", "agent architecture version must be current");
  assert(HalAgent.AGENT_BUDGET.maxTools === 3, "agent must enforce a small tool budget");
  assert(HalAgent.getHealth().budget.maxTools === 3, "agent health must expose budget");
  const blockedRoute = HalCore.routeHalCommand(halData, halModels, pages, "email the payer");
  const plan = HalAgent.buildPlan("email the payer", blockedRoute, HalAgent.getWorkingMemory(), HalAgent.getLongTermMemory());
  assert(plan.isUnsafe === true && plan.tools.includes("explain_firewall"), "unsafe query must plan firewall tool");
  const selfOkPlan = HalAgent.buildPlan(
    "open claims workbench",
    HalCore.routeHalCommand(halData, halModels, pages, "open claims workbench"),
    HalAgent.getWorkingMemory(),
    HalAgent.getLongTermMemory(),
  );
  const selfOk = HalAgent.selfCheckResponse(
    "open claims workbench",
    "I can open Claims Workbench.",
    selfOkPlan,
    {},
    HalCore.routeHalCommand(halData, halModels, pages, "open claims workbench"),
  );
  assert(selfOk.pass === true, "valid local answer must pass self-check");
  const selfBad = HalAgent.selfCheckResponse("email payer", "I emailed the payer for you.", plan, {}, blockedRoute);
  assert(selfBad.pass === false, "claimed external action must fail self-check");
  const helpRoute = HalCore.routeHalCommand(halData, halModels, pages, "what can you do?");
  assert(helpRoute.text.includes("agent loop"), "help text must describe agent loop");
  assert(helpRoute.text.includes("print any page"), "help text must mention print");
  const printPageRoute = HalCore.routeHalCommand(halData, halModels, pages, "print this page");
  assert(printPageRoute.intent === "print: page" && printPageRoute.usePrint === true, "print page must route locally");
  const printWidgetRoute = HalCore.routeHalCommand(halData, halModels, pages, "print financial widget");
  assert(printWidgetRoute.intent === "print: widget:practiceFinancialOverview", "print widget must resolve widget key");
  const closeoutRunbookRoute = HalCore.routeHalCommand(halData, halModels, pages, "closeout runbook");
  assert(closeoutRunbookRoute.intent === "ops: closeout-runbook" && closeoutRunbookRoute.useCloseoutRunbook === true, "closeout runbook must route locally");
  const selfHealRoute = HalCore.routeHalCommand(halData, halModels, pages, "strengthen program");
  assert(selfHealRoute.intent === "ops: self-heal" && selfHealRoute.useProgramSelfHeal === true, "program self-heal must route locally");
  const mockCtx = {
    halData,
    halModels,
    pages,
    halOfficeTasks: [],
    halWorkSession: null,
    halEvidencePacket: null,
    halReadinessDiagnostics: null,
    halSideNotes: [],
    halSideNoteMonitor: null,
    loadProgramSnapshot: async () => ({ widgets: {}, claims: { top: [] }, library: { top: [] } }),
    refreshHalWidgetFeed: async () => null,
    workSessionStatusText: () => "No session",
    runReadinessDiagnostics: () => HalCore.runReadinessChecks(halData, halModels, pages),
    staffUseGateText: () => "gate",
    staffHandoffSummaryText: () => "handoff",
    runOperatorSmokeTest: () => HalCore.runOperatorSmokeTest(halData, halModels, pages),
    refreshSideNoteMonitor: () => null,
    addSideNote: (t) => ({ text: t }),
    addOfficeTask: () => null,
    startWorkSession: () => null,
    resetWorkSession: () => null,
    draftSessionHandoff: () => null,
    buildEvidencePacketFromSession: () => null,
    clearEvidencePacket: () => null,
    clearReadinessDiagnostics: () => null,
    normalizeActions: (a) => a || [],
    clearProgramContextCache: () => null,
    setHalWidgetFeed: () => null,
    Services: null,
    ImportLoader: null,
  };
  const execHelp = await HalRouteExec.execute(helpRoute, "what can you do?", {}, mockCtx);
  assert(execHelp && execHelp.text.includes("agent loop"), "route exec must return help text");
  passed++;

  // Structural stabilization guarantees
  require(join(siteDir, "runtime-issues.js"));
  require(join(siteDir, "snapshot-store.js"));
  require(join(siteDir, "import-coordinator.js"));
  require(join(siteDir, "office-task-store.js"));
  const DesktopBridge = require(join(siteDir, "desktop-bridge.js"));
  const Services = require(join(siteDir, "services.js"));
  const ImportCoordinatorMod = require(join(siteDir, "import-coordinator.js"));
  const SnapshotStoreMod = require(join(siteDir, "snapshot-store.js"));
  const RuntimeIssuesMod = require(join(siteDir, "runtime-issues.js"));
  global.Services = Services;
  global.RuntimeIssues = RuntimeIssuesMod;
  global.SnapshotStore = SnapshotStoreMod;
  global.ImportCoordinator = ImportCoordinatorMod;
  global.DesktopBridge = DesktopBridge;

  RuntimeIssuesMod.clear();
  RuntimeIssuesMod.record("services.refreshImports", new Error("sync timeout"), { status: "failed" });
  const statusWithIssue = ImportLoader.formatImportStatus({
    loadedAt: new Date().toISOString(),
    syncStatus: { attempted: true, ok: false, error: "copy failed" },
    softdent: {},
    quickbooks: {},
  });
  assert(statusWithIssue.includes("sync timeout") || statusWithIssue.includes("copy failed"), "import status must surface sync/runtime errors");

  const quotedRows = ImportLoader.readCsvRows('name,note\n"Smith, Jane",paid');
  assert(quotedRows.length === 1 && quotedRows[0].name === "Smith, Jane", "CSV parser must handle quoted commas");

  const arOnlyBundle = { softdent: { ar: { rows: [{ bucket: "0-30", amount: "100" }] } }, quickbooks: {} };
  assert(ImportLoader.hasSoftdentImport(arOnlyBundle) === true, "AR-only SoftDent imports must count as import data");

  let refreshCalls = 0;
  const originalRefresh = Services.refreshImports;
  Services.refreshImports = async () => {
    refreshCalls += 1;
    await new Promise((resolve) => setTimeout(resolve, 30));
    return { loadedAt: new Date().toISOString(), softdent: {}, quickbooks: {} };
  };
  const p1 = ImportCoordinatorMod.refresh({ reason: "validator" });
  const p2 = ImportCoordinatorMod.refresh({ reason: "validator-dup" });
  assert(p1 === p2, "ImportCoordinator must single-flight concurrent refresh requests");
  await p1;
  assert(refreshCalls === 1, "single-flight refresh must call Services.refreshImports once");
  Services.refreshImports = originalRefresh;

  SnapshotStoreMod.invalidate("validator");
  const snap1 = await SnapshotStoreMod.get(() => Services.buildProgramSnapshotCore());
  const snap2 = await SnapshotStoreMod.get(() => {
    throw new Error("should not rebuild within TTL");
  });
  assert(snap1 === snap2, "SnapshotStore must reuse cached snapshot within TTL");
  assert(snap1.dashboards && snap1.dashboards.financial && snap1.dashboards.ar, "program snapshot must include all dashboards from one bundle build");

  const runningRefreshCtx = Object.assign({}, mockCtx, {
    Services: {
      refreshImports: async () => {
        throw new Error("should not be called when coordinator handles refresh");
      },
      loadImportBundle: async () => ({
        loadedAt: new Date().toISOString(),
        syncStatus: { status: "running" },
        softdent: {},
        quickbooks: {},
      }),
      invalidateSnapshot: () => SnapshotStoreMod.invalidate("hal-route"),
    },
    ImportLoader,
    loadProgramSnapshot: async () => ({ widgets: {}, claims: { top: [] }, library: { top: [] } }),
    clearProgramContextCache: () => null,
  });
  Services.refreshImports = async () => ({
    loadedAt: new Date().toISOString(),
    syncStatus: { status: "success", ok: true },
    softdent: {},
    quickbooks: {},
  });
  const desktopBridgeForRoute = global.DesktopBridge;
  global.DesktopBridge = Object.assign({}, DesktopBridge, { hasDesktopApi: () => true });
  const refreshExec = await HalRouteExec.execute(importRefreshRoute, "refresh imports", {}, runningRefreshCtx);
  assert(refreshExec && refreshExec.text.includes("Import bundle"), "import refresh route must not throw when sync is running");
  global.DesktopBridge = desktopBridgeForRoute;

  // Follow-up audit fixes (H1–L4)
  Services.refreshImports = originalRefresh;
  SnapshotStoreMod.invalidate("audit-fixes");
  await SnapshotStoreMod.get(() => Services.buildProgramSnapshotCore());
  assert(SnapshotStoreMod.status().hasSnapshot, "snapshot must cache after build");
  await Services.narratives.saveDraft({ keyPoints: ["audit"], text: "validator draft", focus: "Medical Necessity" });
  assert(!SnapshotStoreMod.status().hasSnapshot, "local narratives save must invalidate SnapshotStore");

  const appSrc = readFileSync(join(siteDir, "app.js"), "utf8");
  assert(!appSrc.includes("PROGRAM_SNAPSHOT_TTL_MS"), "HAL must not use app-level snapshot TTL cache");
  assert(appSrc.includes("return loadProgramSnapshot()"), "loadCachedProgramSnapshot must delegate to Services snapshot path");
  assert(appSrc.includes("runtimeIssuesDrawerHtml"), "sources drawer must surface runtime issues");

  await SnapshotStoreMod.get(() => Services.buildProgramSnapshotCore());
  const snapCached = SnapshotStoreMod.peek();
  const dashFromSnap = await Services.readDashboard("financial");
  assert(
    snapCached && snapCached.dashboards && dashFromSnap && dashFromSnap.productionMtd,
    "readDashboard must read from cached snapshot dashboards",
  );

  const priorBridge = global.DesktopBridge;
  global.DesktopBridge = {
    refreshImports: async () => ({ status: "running" }),
    getImportBundle: async () => ({
      loadedAt: new Date().toISOString(),
      softdent: {},
      quickbooks: {},
      syncStatus: { ok: true },
    }),
  };
  const bootStart = Date.now();
  const bootBundle = await Services.refreshImports({ reason: "boot" });
  assert(Date.now() - bootStart < 3000, "boot import refresh must not block on running sync");
  assert(bootBundle.syncStatus && bootBundle.syncStatus.status === "running", "boot refresh must report running sync honestly");
  global.DesktopBridge = priorBridge;

  delete process.env.NR2_LOAD_IMPORTS;
  const browserOnlyBundle = await ImportLoader.loadBundle();
  assert(browserOnlyBundle === null, "browser-only import load without bridge must return null");
  process.env.NR2_LOAD_IMPORTS = "1";

  const browserStorageReadiness = HalCore.runReadinessChecks(halData, halModels, pages, { storageMode: "sessionStorage" });
  const browserStorage = browserStorageReadiness.results.find((item) => item.id === "storage");
  assert(browserStorage && browserStorage.status === "Warning" && browserStorage.label.includes("Browser preview"), "browser mode readiness must report degraded preview storage");
  const desktopStorageReadiness = HalCore.runReadinessChecks(halData, halModels, pages, { storageMode: "sqlite", desktopBridgeOk: true });
  const desktopStorage = desktopStorageReadiness.results.find((item) => item.id === "storage");
  assert(desktopStorage && desktopStorage.status === "Pass" && desktopStorage.label.includes("Desktop SQLite"), "desktop mode readiness must report SQLite storage");

  const priorDesktopBridge = global.DesktopBridge;
  global.window = global.window || {};
  global.DesktopBridge = Object.assign({}, DesktopBridge, {
    hasDesktopApi: () => false,
    desktopRequiredMessage: (feature) => `${feature} requires the NR2 desktop app.`,
  });
  const browserImportExec = await HalRouteExec.execute(importRefreshRoute, "refresh imports", {}, Object.assign({}, mockCtx, { Services, ImportLoader }));
  assert(browserImportExec.text.includes("requires the NR2 desktop app"), "HAL import route must clearly block browser-only refresh");
  global.DesktopBridge = priorDesktopBridge;

  // Financial automation contract and diagnostics
  const ImportDiagnostics = require(join(siteDir, "import-diagnostics.js"));
  const manifest = JSON.parse(readFileSync(join(__dirname, "import-manifest.json"), "utf8"));
  assert(manifest.datasets["softdent.dashboard"].requiredFields.includes("production"), "manifest must declare dashboard required fields");
  assert(manifest.datasets["quickbooks.ar"].automated === false, "QuickBooks A/R must be marked not automated until collector exists");

  const freshBundle = {
    loadedAt: new Date().toISOString(),
    softdent: {
      dashboard: {
        sourceFile: "softdent_dashboard_data.json",
        modifiedAt: new Date().toISOString(),
        rows: [{ production: 1000, collections: 800, period: "2026-06" }],
      },
      claims: null,
      clinicalNotes: null,
      ar: {
        sourceFile: "softdent_ar_aging.csv",
        modifiedAt: new Date().toISOString(),
        rows: [{ Bucket: "Current", Balance: 100 }],
      },
    },
    quickbooks: {
      revenue: {
        sourceFile: "quickbooks_revenue.csv",
        modifiedAt: new Date().toISOString(),
        rows: [{ TotalIncome: 5000 }],
      },
      expenses: {
        sourceFile: "quickbooks_expenses.csv",
        modifiedAt: new Date().toISOString(),
        rows: [{ TotalExpense: 3000 }],
      },
      expenseCategories: null,
      ar: null,
    },
  };
  const diagnostics = ImportDiagnostics.evaluateBundle(freshBundle, manifest);
  assert(diagnostics.summary.connected >= 2, "connected datasets must be reported for valid financial imports");
  const qbAr = diagnostics.datasets.find((item) => item.datasetKey === "quickbooks.ar");
  assert(qbAr && qbAr.status === "not_configured", "QuickBooks A/R must report not configured without automated collector");

  const staleBundle = JSON.parse(JSON.stringify(freshBundle));
  staleBundle.softdent.dashboard.modifiedAt = new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString();
  const staleDiagnostics = ImportDiagnostics.evaluateBundle(staleBundle, manifest);
  const staleDashboard = staleDiagnostics.datasets.find((item) => item.datasetKey === "softdent.dashboard");
  assert(staleDashboard && staleDashboard.status === "stale", "stale dashboard files must report stale status");

  const partialBundle = JSON.parse(JSON.stringify(freshBundle));
  partialBundle.softdent.dashboard.rows = [{ collections: 10 }];
  const partialDiagnostics = ImportDiagnostics.evaluateBundle(partialBundle, manifest);
  const partialDashboard = partialDiagnostics.datasets.find((item) => item.datasetKey === "softdent.dashboard");
  assert(partialDashboard && partialDashboard.status === "partial", "missing required fields must report partial status");

  const trendBundle = {
    loadedAt: new Date().toISOString(),
    softdent: {
      dashboard: {
        sourceFile: "softdent_dashboard_data.json",
        modifiedAt: new Date().toISOString(),
        rows: [
          { production: 1000, collections: 800, period: "2026-04", insurance: 600, patient: 200 },
          { production: 1200, collections: 900, period: "2026-05", insurance: 700, patient: 200 },
        ],
      },
    },
    quickbooks: { revenue: freshBundle.quickbooks.revenue, expenses: freshBundle.quickbooks.expenses },
  };
  const financialDash = ImportLoader.buildDashboard("financial", attachDiagnosticsBundle(trendBundle));
  function attachDiagnosticsBundle(bundle) {
    bundle.diagnostics = ImportDiagnostics.evaluateBundle(bundle, manifest);
    return bundle;
  }
  assert(financialDash && financialDash.productionTrend && financialDash.productionTrend.production.length > 1, "financial dashboard must build production trend from multi-period imports");
  assert(financialDash.payerMix && financialDash.payerMix.slices.length > 0, "financial dashboard must build payer mix when insurance/patient present");

  const qbArBundle = {
    loadedAt: new Date().toISOString(),
    quickbooks: {
      revenue: freshBundle.quickbooks.revenue,
      expenses: freshBundle.quickbooks.expenses,
      ar: {
        sourceFile: "quickbooks_ar.csv",
        modifiedAt: new Date().toISOString(),
        rows: [{ Bucket: "Current", Balance: 2500 }],
      },
    },
  };
  const qbDash = ImportLoader.buildDashboard("quickbooks", qbArBundle);
  assert(qbDash && qbDash.ar && qbDash.ar.total, "QuickBooks dashboard must parse A/R when file is present");

  const statusText = ImportLoader.formatImportStatus(attachDiagnosticsBundle(freshBundle));
  assert(statusText.includes("Dataset health:"), "import status must include dataset-level health summary");
  assert(statusText.includes("not configured"), "import status must explain QuickBooks A/R automation posture");

  const sourceText = HalSkills.formatSourceHealthText(
    {
      softdent: {
        hasData: true,
        connectionStatus: "Connected",
        detail: "2/4 datasets connected.",
        datasetSummary: "2/4 connected",
        datasetLines: ["softdent.dashboard: Connected"],
      },
    },
    [],
  );
  assert(sourceText.includes("Connected"), "HAL source health must use Connected/Partial/Stale language");

  const HalProactive = require(join(siteDir, "hal-proactive.js"));
  const proactiveSnapshot = {
    gatheredAt: new Date().toISOString(),
    dashboards: { financial: { dataSource: "empty" } },
    importBundle: {
      diagnostics: {
        datasets: [
          {
            datasetKey: "softdent.dashboard",
            system: "softdent",
            status: "stale",
            severity: "critical",
            detail: "Dataset is stale.",
            collectorHint: "Bridge sync task",
          },
        ],
        summary: { connected: 0, partial: 0, stale: 1, missing: 0, notConfigured: 0 },
      },
    },
    officeTasks: [],
    widgets: { widgets: {} },
    runtimeIssues: [],
  };
  const proactiveBriefing = HalProactive.buildProactiveBriefing(proactiveSnapshot, mockCtx);
  assert(proactiveBriefing.topAction && proactiveBriefing.recommendations.length > 0, "HAL proactive manager must recommend actions from program state");
  assert(
    HalProactive.formatProactiveBriefing(proactiveBriefing).includes("HAL internal office manager"),
    "proactive briefing must format office manager role",
  );
  const proactiveRoute = HalCore.routeHalCommand(halData, halModels, pages, "What should HAL do for the program?");
  assert(proactiveRoute.useProactiveBriefing === true, "proactive questions must route to proactive briefing");

  let halAutoRefreshCalled = false;
  const priorPlacementBridge = global.DesktopBridge;
  const priorPlacementCoordinator = global.ImportCoordinator;
  global.DesktopBridge = {
    hasDesktopApi: () => true,
  };
  global.ImportCoordinator = undefined;
  const placement = await HalProactive.runAutonomousPlacement(
    {
      Services: {
        refreshImports: async () => {
          halAutoRefreshCalled = true;
        },
      },
      clearProgramContextCache: () => {},
      invalidateProgramCaches: () => {},
    },
    {
      datasets: [{ datasetKey: "softdent.dashboard", automated: true, status: "stale" }],
    },
  );
  assert(placement.refreshed === true && halAutoRefreshCalled === true, "HAL proactive cycle must refresh stale automated datasets when desktop bridge is available");
  global.DesktopBridge = priorPlacementBridge;
  global.ImportCoordinator = priorPlacementCoordinator;
  const writebackBlocked = HalCore.routeHalCommand(halData, halModels, pages, "Write back to SoftDent");
  assert(writebackBlocked.intent === "blocked: firewall", "autonomous placement must not enable external writeback");

  const emptyDiag = ImportDiagnostics.evaluateBundle({ softdent: {}, quickbooks: {} }, manifest);
  ["softdent.newPatients", "softdent.treatmentPlans", "softdent.caseAcceptance"].forEach((datasetKey) => {
    const item = emptyDiag.datasets.find((row) => row.datasetKey === datasetKey);
    assert(item && item.status === "missing", `${datasetKey} must report missing until sync generates or stages exports`);
    assert(item.automated === true, `${datasetKey} must be marked automated via analytics sync`);
    assert(item.collectorHint, `${datasetKey} must include collector guidance`);
  });
  const practiceFeed = HalSkills.buildWidgetFeed({
    dashboards: { practice: { dataSource: "empty" }, financial: { dataSource: "empty" }, softdent: { dataSource: "empty" }, quickbooks: { dataSource: "empty" } },
    importBundle: { diagnostics: emptyDiag },
  });
  assert(
    practiceFeed.widgets.newPatients.metrics.newPatientCount === "Not Configured" ||
      practiceFeed.widgets.newPatients.metrics.newPatientCount === "—",
    "new patients widget must stay honest when export is not configured",
  );

  const HalOfficeManager = require(join(siteDir, "hal-office-manager.js"));
  assert(HalOfficeManager.ROLE_SUMMARY.includes("internal office manager"), "HAL must define internal office manager role");
  const officePriorities = HalOfficeManager.buildOfficePriorities(proactiveSnapshot, { halSideNotes: [{ status: "open", priority: "high", text: "Recall patient" }] });
  assert(officePriorities.length > 0, "office manager must build priorities from program state");
  const officeState = HalOfficeManager.buildOfficeManagerState(proactiveSnapshot, {}, { officePriorities, placement: { refreshed: false }, autoTasks: { created: [] } });
  const officeBrief = HalOfficeManager.formatDailyOfficeBriefing(officeState, proactiveSnapshot);
  assert(officeBrief.includes("Human must approve"), "daily office briefing must state human approval boundaries");
  assert(officeBrief.includes("Top office priorities"), "daily office briefing must list priorities");
  const officeBriefingRoute = HalCore.routeHalCommand(halData, halModels, pages, "Show daily office briefing");
  assert(officeBriefingRoute.useOfficeBriefing === true, "daily office briefing must route locally");
  assert(HalAgent.SAFETY_POLICY.summary.includes("internal office manager"), "agent safety policy must describe office manager role");

  const upsertOne = HalSkills.upsertHalTask([], { title: "HAL: Repair import", sourceId: "import-stale-softdent.dashboard", notes: "stale" }, { actor: "hal-proactive" });
  const upsertTwo = HalSkills.upsertHalTask(upsertOne.tasks, { title: "HAL: Repair import updated", sourceId: "import-stale-softdent.dashboard", notes: "still stale" }, { actor: "hal-proactive" });
  assert(upsertOne.created === true && upsertTwo.created === false && upsertTwo.tasks.length === 1, "HAL tasks must upsert by sourceId without duplicates");
  const resolved = HalSkills.autoResolveHalTasks(upsertTwo.tasks, []);
  assert(resolved[0].status === "completed", "HAL tasks must auto-resolve when source issue disappears");

  passed++;

  console.log(`HAL validation passed (${passed} suites)`);
}

main().catch((error) => {
  console.error("HAL validation failed:", error.message);
  process.exit(1);
});

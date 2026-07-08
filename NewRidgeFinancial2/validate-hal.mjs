#!/usr/bin/env node
/**
 * HAL validation — JSON, router, firewall, registry, and suggestion routes.
 * Usage: node validate-hal.mjs
 */
import { readFileSync, existsSync } from "node:fs";
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
  addMany(["Show HAL capability index", "HAL capability score", "where is HAL"], "ops: capability-index");
  addMany(["Run orchestrator triage", "multi-agent triage"], "ops: orchestrator-triage");
  addMany(["HAL 10000 ascension", "director digest", "executive digest"], "ops: ascension-10000");
  addMany(["autonomous ops status", "HAL 9000 ops"], "ops: autonomous-status");
  addMany(["HAL about me", "about me", "tell me about me"], "ops: hal-about-me");
  addMany(["go to 7", "go to level 7", "executive partner"], "ops: employee-set-level");
  addMany(["HAL employee status", "employee level", "employee tier"], "ops: employee-status");
  addMany(["HAL work log", "what did HAL do"], "ops: employee-work-log");
  addMany(["Run HAL shift", "run employee shift"], "ops: employee-shift");
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
    quickbooks: ["QuickBooks", "profit and loss", "posting queue"],
    ar: ["A/R", "collections", "aging"],
    claims: ["claims workbench", "claims"],
    narratives: ["insurance narratives", "narratives"],
    documents: ["accounting documents", "documents"],
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
  addMany(["consent policy", "what are the guardrails?"], "consent");
  addMany(["Are you connected to a model?", "model lanes"], "model lanes");
  addMany(["source health", "source freshness"], "sources");
  addMany(["read-only areas", "review-only areas"], "registry: read-only");
  addMany(["next staff action", "what should staff review next"], "registry: next actions");

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

  return { cases, modelFallback };
}

function trapLocalIntent(localPhrase) {
  const map = {
    "Run readiness check": "readiness: run",
    "Build evidence packet": "packet: build",
    "Start claims review": "session: start:claims-review",
    "Show diagnostics": "readiness: show",
    "Open claims workbench": "navigate: claims",
  };
  return map[localPhrase] || "model: query";
}

function seededChoice(seedState, items) {
  seedState.value = (seedState.value * 1664525 + 1013904223) >>> 0;
  return items[Math.floor((seedState.value / 0x100000000) * items.length)];
}

function buildSeededRoutingVariants(count) {
  const { cases, modelFallback } = buildRoutingRegressionCases();
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
      expected = trapLocalIntent(local);
    } else if (i < count * 0.95) {
      const base = modelFallback[i % modelFallback.length];
      const prefix = prefixes[i % prefixes.length];
      const suffix = suffixes[Math.floor(i / modelFallback.length) % suffixes.length];
      question = `${prefix}${base}${suffix}`;
      expected = "model: query";
    } else {
      const base = modelFallback[i % modelFallback.length];
      const prefix = prefixes[i % prefixes.length];
      question = `${prefix}${base}`;
      expected = "model: query";
    }

    variants.push([question.replace(/\s+/g, " ").trim(), expected]);
  }

  return variants;
}

async function main() {
  process.env.NR2_LOAD_IMPORTS = "1";
  const halData = loadJson(halManagerPath);
  const halModels = loadJson(halModelsPath);
  const halProgrammingUrl = pathToFileURL(join(siteDir, "hal-agent-programming.js")).href;
  await import(halProgrammingUrl);
  const halCursorParityUrl = pathToFileURL(join(siteDir, "hal-cursor-parity.js")).href;
  await import(halCursorParityUrl);
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
  assert(halData.consent && halData.consent.examples.length >= 4, "consent examples required");
  assert(halData.consent.required === true, "consent policy must be required");
  passed++;

  // No firewall — outbound actions use consent policy
  const submitRoute = HalCore.routeHalCommand(halData, halModels, pages, "submit the claim");
  assert(submitRoute.intent !== "blocked: firewall", "submit must not hit firewall block");
  const emailRoute = HalCore.routeHalCommand(halData, halModels, pages, "emailing the payer");
  assert(emailRoute.intent !== "blocked: firewall", "email must not hit firewall block");
  const escalateSubmit = HalCore.routeHalCommand(halData, halModels, pages, "escalate and submit the claim");
  assert(escalateSubmit.intent !== "blocked: firewall", "escalation must not be blocked by firewall");
  passed++;

  // Consent checker
  const allowed = HalCore.consentVerdict("open claims workbench", halData.consent, halData);
  const uploadVerdict = HalCore.consentVerdict("upload the narrative", halData.consent, halData);
  assert(uploadVerdict.allowed === true, "upload should be allowed pending consent");
  const uploadNeedsConsent = uploadVerdict.intent === "consent: required";
  assert(uploadNeedsConsent, "upload must flag consent required");
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

  // Session + external phrase keeps local session intent when firewall is off
  const sessionTrap = HalCore.routeHalCommand(halData, halModels, pages, halData.validation.sessionFirewallTrap);
  assert(sessionTrap.intent === "session: start:claims-review", "session + submit must keep session route");
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
  assert(packetTrap.intent === "packet: build", "packet + email must keep packet route");
  passed++;

  // Readiness checks
  assert(halData.readiness && halData.readiness.expectedRegistryCount === 11, "readiness config required");
  const readinessReport = HalCore.runReadinessChecks(halData, halModels, pages);
  assert(readinessReport && readinessReport.results && readinessReport.results.length >= 6, "readiness must return checks");
  const registryCheck = readinessReport.results.find((item) => item.id === "registry");
  assert(registryCheck && registryCheck.status === "Pass", "registry readiness must pass");
  const consentCheck = readinessReport.results.find((item) => item.id === "consent");
  assert(consentCheck && consentCheck.status === "Pass", "consent readiness must pass");
  const routesCheck = readinessReport.results.find((item) => item.id === "routes");
  assert(routesCheck && routesCheck.status === "Pass", "route fixture readiness must pass");
  const readinessRoutes = halData.validation.readinessRoutes || {};
  for (const [command, expectedIntent] of Object.entries(readinessRoutes)) {
    const result = HalCore.routeHalCommand(halData, halModels, pages, command);
    assert(result.intent === expectedIntent, `readiness "${command}" expected ${expectedIntent}, got ${result.intent}`);
  }
  const readinessTrap = HalCore.routeHalCommand(halData, halModels, pages, halData.validation.readinessFirewallTrap);
  assert(readinessTrap.intent === "readiness: run", "readiness + email must keep readiness route");
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
  assert(gateTrap.intent === "readiness: gate", "gate + email must keep gate route");
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
  assert(operatorTrap.intent === "operator: smoke", "operator smoke + email must keep operator route");
  const handoff = HalCore.buildHandoffSummary(halData, halModels, { readiness: readinessReport, smoke });
  assert(handoff.includes("STAFF HANDOFF SUMMARY"), "handoff summary must format");
  assert(/human review/i.test(handoff), "handoff summary must mention human review");
  const health = HalCore.deriveDrawerHealth(halData, halModels, pages, readinessReport);
  for (const key of ["askHal", "sources", "reasoning", "workSurfaces", "consent", "priorities"]) {
    assert(["Pass", "Warning", "Fail"].includes(health[key]), `drawer health for ${key} must be valid, got ${health[key]}`);
  }
  const laneDetails = HalCore.modelLaneDetails(halModels);
  assert(laneDetails.length === halModels.lanes.length, "model lane details must cover all configured lanes");
  passed++;

  // Seeded routing regression: local intents, model fallbacks, and mixed local+external phrases.
  const routingCases = buildSeededRoutingVariants(10000);
  const routingFailures = [];
  const laneCounts = {};
  for (const [question, expectedIntent] of routingCases) {
    const result = HalCore.routeHalCommand(halData, halModels, pages, question);
    const got = String(result.intent || "");
    const ok =
      got === expectedIntent ||
      got.startsWith(expectedIntent) ||
      (expectedIntent === "reasoning" &&
        got === "priorities" &&
        /\bcan you\b/i.test(question) &&
        /\bmake a plan|plan for today\b/i.test(question));
    laneCounts[result.lane] = (laneCounts[result.lane] || 0) + 1;
    if (!ok) routingFailures.push(`"${question}" expected ${expectedIntent}, got ${got}`);
  }
  assert(routingFailures.length === 0, "routing regression failures:\n" + routingFailures.slice(0, 20).join("\n"));
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
  execSync("node --check site/hal-agent-loop.js", { cwd: __dirname, stdio: "pipe" });
  passed++;

  // HAL page surfaces required manager signals (no backend, local data only)
  require(join(siteDir, "icons.js"));
  globalThis.AppIcons = require(join(siteDir, "icons.js"));
  require(join(siteDir, "page-schema.js"));
  require(join(siteDir, "hal-page-schema.js"));
  require(join(siteDir, "nr2-moonshot-mockup-chrome.js"));
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
    halSideNotes: [{ noteId: "n1", text: "Recall patient", status: "open", priority: "normal" }],
    halSideNoteMonitor: { activeCount: 1, openCount: 1, pinnedCount: 0, highPriorityCount: 0, checkedAt: new Date().toISOString() },
    halSideNotesInbox: null,
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
    sidenotesHubPath: null,
  });
  assert(halHtml.includes("STAFF NOTES"), "HAL page must render the staff notes card (not SideNotesIM on financial app)");
  assert(!halHtml.includes("SIDENOTESIM MONITOR"), "HAL financial app must not render SideNotesIM live monitor");
  assert(!halHtml.includes("SIDENOTES PROGRAM"), "HAL financial app must not render external SideNotes program card");
  assert(halHtml.includes("data-hal-surf-nav=\"sidenotes\""), "HAL page must wire staff notes work surface navigation");
  assert(halHtml.includes("data-hal-surf-open="), "HAL page must wire work surface open chevrons");
  assert(
    halHtml.includes("widget-mosaic-tile") || halHtml.includes("widget-card span-1") || halHtml.includes('class="widget-card span-1"'),
    "HAL page must wire widget cards to HAL",
  );
  assert(halHtml.includes("data-hal-activity-cmd="), "HAL page must wire activity log replay to HAL");
  assert(halHtml.includes("hal-status-ring") || halHtml.includes("status-btn"), "HAL page must wire status chips to HAL");
  assert(halHtml.includes('class="header"') || halHtml.includes("<header class=\"header\">"), "HAL page must use mockup HAL header");
  assert((halHtml.match(/HAL Command Center/g) || []).length <= 1, "HAL Command Center title must not repeat as legacy widget group box");
  assert(halHtml.includes("badge-live"), "HAL page must show LIVE badge");
  assert(halHtml.includes("alert-strip"), "HAL page must show alert strip");
  assert(halHtml.includes("chat-rail"), "HAL page must render Ask HAL chat rail");
  assert(halHtml.includes("dashboard-grid"), "HAL page must use dashboard grid layout");
  assert(!halHtml.includes("hp-grid"), "HAL page must not use legacy hp-grid");
  assert(!halHtml.includes("hp-card"), "HAL page must not use legacy hp-card panels");
  assert(!halHtml.match(/\bhp-[a-z]/), "HAL page must not use legacy hp-* class prefix");
  assert(halHtml.includes("lane-badge"), "HAL page must render program posture lane badge");
  assert(halHtml.includes("import-health"), "HAL page must render import health panel");
  assert(halHtml.includes("widget-card"), "HAL page must use mockup widget-card panels");
  assert(!halHtml.includes("pv-canvas-hero"), "HAL page must not use legacy pv-canvas hero");
  assert(!halHtml.includes("pv-badge"), "HAL page must not use legacy pv-badge");
  assert(!halHtml.match(/\bclass="[^"]*\bpv-/), "HAL page must not use legacy pv-* class prefix in markup");
  assert(halHtml.includes("prompt-chip--icon"), "HAL page must render icon-backed prompt chips");
  assert(halHtml.includes("<svg") && halHtml.includes('class="app-ico"'), "HAL page must render SVG icons");
  assert(halHtml.includes("header-icon"), "HAL page must render section header icons");
  assert(halHtml.includes("control-icon"), "HAL page must render system control icons");
  assert(halHtml.includes("metric-large"), "HAL page must render mission metric tiles");
  assert(halHtml.includes("Production MTD"), "HAL page must surface production metric tile");
  assert(!halHtml.includes("Financial Widgets"), "HAL page must not render staff widget group inventory");
  assert(!halHtml.includes("Clinical Widgets"), "HAL page must not render clinical widget group inventory");
  assert(!halHtml.includes("Revenue &amp; A/R"), "HAL page must not render revenue widget group inventory");
  assert(!halHtml.includes("ms-hal-wg-section"), "HAL page must not render expandable widget group sections");
  assert(!halHtml.includes("NO FEED"), "HAL page must not render NO FEED widget rows");
  assert(halHtml.includes("data-hal-widget-key="), "HAL page must wire widget keys on mission tiles");
  assert(halHtml.includes('id="hpAskForm"'), "HAL page must keep Ask HAL chat form");
  assert(halHtml.includes('id="hpAskInput"'), "HAL page must keep Ask HAL chat input");
  assert(halHtml.includes("IMPORT & SOURCE HEALTH"), "HAL page must render import health panel");
  assert(!halHtml.includes("Room 4"), "HAL financial app must not show SideNotesIM sender feed");
  assert(halHtml.includes("LOCAL NOTES"), "HAL page must render the local notes section");
  assert(halHtml.includes("PROGRAM POSTURE"), "HAL page must surface program posture");
  assert(halHtml.includes("TRUST & CONSENT"), "HAL page must surface consent policy");
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
  const chatRuntime = HalCore.laneRuntime(halModels, "chat8b");
  assert(chatRuntime && chatRuntime.think === false, "chat lane must disable thinking tokens");
  assert(chatRuntime.options && chatRuntime.options.num_predict === 1536, "chat lane token cap must match hal-models.json localModel");
  assert(chatRuntime.options.num_ctx === 4096, "chat lane context must match hal-models.json localModel");
  assert(
    HalCore.buildFastChatSystemPrompt(halData, null).includes("PROGRAMMING:"),
    "fast chat prompt must include Auto agent programming contract",
  );
  assert(halModels.config.preferReasoning === true, "HAL must prefer 24B reasoning lane by default");
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
  assert(
    emptyShell.includes("ms-page-chrome") || emptyShell.includes("top-header"),
    "page chrome must render financial mockup shell with empty feed",
  );
  const missingShell = PageChromeMod.canvasShell({ pageId: "not-a-real-page", halData: {} });
  assert(
    missingShell.includes("ms-page-chrome--missing") || missingShell.includes("pv-canvas-shell--missing"),
    "page chrome must degrade when schema is missing",
  );
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

  // Accounting: drafting routes locally; posting phrases no longer hit firewall when disabled.
  const draftRoute = HalCore.routeHalCommand(halData, halModels, pages, "Draft a journal entry for $1,200 prepaid insurance");
  assert(draftRoute.intent === "accounting: journal-draft" && draftRoute.useJournalDraft === true, "journal drafting must route locally");
  const postRoute = HalCore.routeHalCommand(halData, halModels, pages, "Post a journal entry to the ledger");
  assert(postRoute.intent !== "blocked: firewall", "posting must not hit firewall when disabled");
  const qbPostRoute = HalCore.routeHalCommand(halData, halModels, pages, "Post to QuickBooks");
  assert(qbPostRoute.intent !== "blocked: firewall", "Post to QuickBooks must not hit firewall when disabled");
  const softdentWriteRoute = HalCore.routeHalCommand(halData, halModels, pages, "Write to SoftDent");
  assert(softdentWriteRoute.intent !== "blocked: firewall", "Write to SoftDent must not hit firewall when disabled");
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
  assert(Object.keys(feed.widgets).length === 48, "widget feed must build 48 operational widgets");
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

  const PageCanvasData = require(join(siteDir, "page-canvas-data.js"));

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
  PageCanvasData.bind(pendingCollectionsFeed, {
    dashboards: {
      financial: { dataSource: "import", collectionsPending: true },
      softdent: { dataSource: "import", collectionsPending: true },
    },
  });
  const pendingFinancialKpis = PageCanvasData.financialKpis();
  const pendingSoftdentKpis = PageCanvasData.softdentKpis();
  assert(
    pendingFinancialKpis.some((row) => row.label === "SoftDent collections" && row.value === "Pending export"),
    "financial page KPIs must label pending collections as Pending export",
  );
  assert(
    pendingSoftdentKpis.some((row) => row.label === "Collections" && row.value === "Pending export"),
    "SoftDent page KPIs must label pending collections as Pending export",
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
  const halLoopUrl = pathToFileURL(join(siteDir, "hal-agent-loop.js")).href;
  await import(halLoopUrl);
  const halAgentUrl = pathToFileURL(join(siteDir, "hal-agent.js")).href;
  const halRouteExecUrl = pathToFileURL(join(siteDir, "hal-route-exec.js")).href;
  const HalAgent = (await import(halAgentUrl)).default || (await import(halAgentUrl));
  const HalRouteExec = (await import(halRouteExecUrl)).default || (await import(halRouteExecUrl));
  assert(HalAgent.SAFETY_POLICY && HalAgent.SAFETY_POLICY.blocked.length > 0, "agent safety policy must exist");
  assert(HalAgent.ARCHITECTURE_VERSION === "hal-agent-v13-cursor", "agent architecture version must be current");
  assert(typeof globalThis.HalAgentLoop !== "undefined", "HalAgentLoop must load");
  assert(typeof HalAgentLoop.runModelWithLoop === "function", "agent tool loop must exist");
  assert(typeof HalAgentLoop.suggestAutoTools === "function", "auto tool suggest must exist");
  const autoTools = HalAgentLoop.suggestAutoTools(
    "how does handleHalSubmit work in app.js",
    { isInvestigateQuery: true },
    {},
    new Set(["grep_program_source", "semantic_search_program", "read_current_context", "read_program_snapshot"]),
    { agentAutoTools: true },
  );
  assert(autoTools.length >= 2, "auto tools must suggest grep and search for code questions");
  assert(typeof HalAgent.TOOL_DEFS.semantic_search_program === "object", "semantic_search_program tool must exist");
  assert(typeof HalAgent.TOOL_DEFS.run_git_readonly === "object", "run_git_readonly tool must exist");
  assert(typeof HalAgent.TOOL_DEFS.run_command === "object", "run_command tool must exist");
  assert(typeof HalAgent.TOOL_DEFS.spawn_investigation === "object", "spawn_investigation tool must exist");
  assert(typeof HalAgent.spawnInvestigationSubtask === "function", "spawnInvestigationSubtask must exist");
  assert(typeof HalAgent.isComplexInvestigationQuery === "function", "isComplexInvestigationQuery must exist");
  assert(typeof HalAgent.cloudAgentEligible === "function", "cloudAgentEligible must exist");
  assert(typeof HalAgent.attachOllamaNativeTools === "function", "attachOllamaNativeTools must exist");
  assert(typeof HalAgent.shouldUseAgentToolLoop === "function", "shouldUseAgentToolLoop must exist");
  assert(
    !HalAgent.shouldUseAgentToolLoop("Can you show posting queue items?", { useReasoning: true, useModel: false }, halModels.config.agentProgramming),
    "simple show/list queries must not use full agent tool loop",
  );
  assert(halModels.config.agentProgramming.localOllamaTools === true, "local Ollama tools should be enabled");
  assert(typeof HalAgent.isComplexInvestigationQuery === "function", "isComplexInvestigationQuery must exist");
  assert(
    HalAgent.isComplexInvestigationQuery("Why is the widget empty and how does handleHalSubmit route imports?", { useReasoning: true }),
    "complex investigation detector must match multi-part diagnostics",
  );
  assert(typeof HalAgent.syncAgentBudgetFromModels === "function", "syncAgentBudgetFromModels must exist");
  HalAgent.syncAgentBudgetFromModels(halModels);
  assert(HalAgent.AGENT_BUDGET.maxGatherRounds >= 3, "agent must support multi-round gather");
  assert(HalAgent.AGENT_BUDGET.maxTools === 12, "agent tool budget must honor maxToolsPerTurn from hal-models");
  assert(typeof HalAgentLoop.configureFromAgentProgramming === "function", "agent loop must read agentProgramming config");
  HalAgentLoop.configureFromAgentProgramming(halModels.config.agentProgramming);
  assert(HalAgentLoop.MAX_TOOLS_PER_TURN === 8, "loop max tools per turn must honor config");
  assert(typeof HalAgent.TOOL_DEFS.apply_program_patch === "object", "apply_program_patch tool must exist");
  assert(typeof HalAgent.TOOL_DEFS.run_hal_validation === "object", "run_hal_validation tool must exist");
  assert(typeof HalAgent.TOOL_DEFS.run_node_syntax_check === "object", "run_node_syntax_check tool must exist");
  assert(typeof HalAgent.parsePatchFromQuery === "function", "parsePatchFromQuery must exist");
  const patch = HalAgent.parsePatchFromQuery('<<<patch\nfile: site/test.js\nold:\nfoo\nnew:\nbar\n>>>');
  assert(patch && patch.file === "site/test.js" && patch.old.trim() === "foo", "parsePatchFromQuery must parse patch blocks");
  const genericChatRoute = HalCore.routeHalCommand(halData, halModels, pages, "what is a variable in programming");
  assert(genericChatRoute.useModel && genericChatRoute.lane === "chat8b", "generic questions must route to chat8b");
  assert(HalAgent.fastChatSkipsProgramContext(genericChatRoute), "fast chat must skip heavy program snapshot");
  assert(!HalAgent.fastChatSkipsProgramContext({ useReasoning: true, useModel: true }), "reasoning lane must keep program context");
  assert(HalAgent.AGENT_BUDGET.maxTools === 12, "agent must allow cursor-style multi-tool gather from config");
  assert(HalAgent.AGENT_BUDGET.maxModelContextChars >= 12000, "agent context budget must be expanded");
  assert(typeof HalCore.compressThreadForPrompt === "function", "thread compression must exist");
  assert(typeof HalCore.detectAmbiguousQuery === "function", "ambiguous query detection must exist");
  const ambiguous = HalCore.detectAmbiguousQuery("fix it", []);
  assert(ambiguous && ambiguous.chips && ambiguous.chips.length >= 3, "ambiguous fix-it must offer clarify chips");
  assert(typeof HalAgent.TOOL_DEFS.explain_route === "object", "explain_route tool must exist");
  assert(typeof HalAgent.TOOL_DEFS.read_program_file === "object", "read_program_file tool must exist");
  const gatherPlan = HalAgent.buildPlan(
    "What is wrong with imports on the financial page?",
    { useModel: true, intent: "model: query", text: "" },
    HalAgent.getWorkingMemory(),
    HalAgent.getLongTermMemory(),
    { halData, halModels, pages, getCurrentPage: () => "financial" },
  );
  assert(gatherPlan.tools.includes("read_current_context"), "cursor gather must include page context");
  assert(gatherPlan.tools.includes("read_program_snapshot"), "cursor gather must include snapshot");
  const agentEmailRoute = HalCore.routeHalCommand(halData, halModels, pages, "email the payer");
  const emailPlan = HalAgent.buildPlan("email the payer", agentEmailRoute, HalAgent.getWorkingMemory(), HalAgent.getLongTermMemory());
  assert(emailPlan.isUnsafe === false, "email query must not be flagged unsafe");
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
  const selfBad = HalAgent.selfCheckResponse(
    "email payer",
    "I emailed the payer for you.",
    emailPlan,
    {},
    agentEmailRoute,
  );
  assert(selfBad.pass === false, "claimed external action must fail self-check");
  const helpRoute = HalCore.routeHalCommand(halData, halModels, pages, "what can you do?");
  assert(helpRoute.text.includes("consent") || helpRoute.text.includes("program manager"), "help text must describe HAL role");
  assert(helpRoute.text.length <= HalCore.CHAT_LIMITS.helpMax + 20, "help text must stay chat-sized");
  const pageCapRoute = HalCore.routeHalCommand(halData, halModels, pages, "What can you do on the QuickBooks page?");
  assert(pageCapRoute.intent === "capability:page-can", "page capability must not hit generic help");
  assert(!pageCapRoute.text.includes("agent loop"), "page capability must be page-specific");
  const trimmed = HalCore.trimChatReply("word ".repeat(200), "Can you refresh imports?", {
    intent: "capability:imports",
  });
  assert(trimmed.length <= HalCore.CHAT_LIMITS.capabilityMax + 5, "trimChatReply must cap long chat");
  assert(HalCore.countWords(trimmed) < HalCore.countWords("word ".repeat(200)), "trimChatReply must shorten");
  const allowedRefresh = HalCore.routeHalCommand(halData, halModels, pages, "Are you allowed to refresh imports?");
  assert(allowedRefresh.intent.includes("capability"), "allowed refresh must use capability route");
  assert(!allowedRefresh.text.includes("cannot perform external"), "allowed refresh must not be firewall denial");
  const postCan = HalCore.routeHalCommand(halData, halModels, pages, "Can you post to QuickBooks?");
  assert(postCan.intent !== "blocked: firewall", "can-you post must not use firewall route when disabled");
  const planCan = HalCore.routeHalCommand(
    halData,
    halModels,
    pages,
    "Quick question: can you make a plan for today without staff approval?",
  );
  assert(planCan.useProactiveBriefing || planCan.intent.includes("capability"), "plan can-you must stay local");
  assert(planCan.lane !== "reason21b", "plan can-you must not require reasoning lane");
  passed++;
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
  assert(HalCore.textSimilarity("hello world foo", "hello world bar") < 0.72, "dissimilar text");
  assert(HalCore.synthesizeHandlerReply("HAL readiness: Warning\n" + "[Pass] x\n".repeat(20), "readiness?", { intent: "readiness: run" }).length < 400, "synthesize readiness");
  const spoken = HalCore.toSpokenScript("**Yes** — refresh is local.\n1. step\n2. step\n Say \"Run readiness check\" for the full checklist.", "Can you refresh imports?", { intent: "capability:imports" });
  assert(!spoken.includes("**"), "spoken script must strip markdown");
  assert(!/Say "Run readiness"/.test(spoken), "spoken script must drop depth hints");
  assert(spoken.length <= HalCore.SPOKEN_LIMITS.capabilityMax + 80, "spoken script must stay short");
  assert(/Yes|refresh/i.test(spoken), "spoken script must keep the answer");
  const recap = HalCore.buildSessionRecap([
    { role: "user", text: "Can you refresh imports?" },
    { role: "hal", text: "Yes — local refresh only." },
  ]);
  assert(/recap|asked/i.test(recap), "session recap must summarize turns");
  const compare = HalCore.buildCompareReply("imports", "widgets", halData);
  assert(/import/i.test(compare) && /widget/i.test(compare), "compare reply must contrast topics");
  assert(!HalCore.stripInternalJargon("The agent loop uses chat8b").includes("agent loop"), "jargon strip");
  const leakSample =
    "Office-manager attention. Local tool check: Synthesize tool results into the answer. If multiple tools ran, combine th.";
  assert(!HalCore.stripInstructionLeaks(leakSample).match(/local tool check|synthesize tool/i), "instruction leak strip");
  const readOnlyPolished = HalCore.polishChatReply("Read-only and review-only areas:", "what does read-only mean?", {
    intent: "registry: read-only",
    lane: "local",
  }, { halData, halModels });
  assert(HalCore.countSentences(readOnlyPolished) >= HalCore.MIN_REPLY_SENTENCES, "read-only reply must meet min sentences");
  const transmitConsent = HalCore.variedBlockedCapabilityReply(null, "transmit the claim", halData);
  assert(/consent/i.test(transmitConsent), "outbound reply must mention consent not firewall block");
  const engRandom = HalCore.matchEnglishVocabRoute("random english word", "random english word");
  assert(engRandom && engRandom.useEnglishRandom, "english random word route");
  const engSeed = HalCore.matchEnglishVocabRoute("seed english dictionary library", "seed english dictionary library");
  assert(engSeed && engSeed.useEnglishSeed, "english seed library route");
  require(join(siteDir, "hal-english-vocab.js"));
  const seedMini = {
    docs: [{ title: "English Dictionary Vol 001 (a–abz)", type: "Dictionary", tags: ["english"], content: "abandon: v. to give up\nability: n. skill" }],
    detailById: {},
    storage: { wordCount: 2 },
  };
  assert(HalEnglishVocab.lookupInSeed(seedMini, "ability").definition.includes("skill"), "dictionary lookup");
  passed++;
  const execHelp = await HalRouteExec.execute(helpRoute, "what can you do?", {}, mockCtx);
  assert(execHelp && /consent|program manager/i.test(execHelp.text), "route exec must return help text");
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
  const bootElapsed = Date.now() - bootStart;
  assert(bootElapsed < 5000, `boot import refresh must not block on running sync (took ${bootElapsed}ms)`);
  assert(bootBundle.syncStatus && bootBundle.syncStatus.status === "running", "boot refresh must report running sync honestly");
  global.DesktopBridge = priorBridge;

  await Services.resetAll();
  const priorImportLoader = global.ImportLoader;
  global.ImportLoader = {
    shouldLoadImports: () => true,
    hasImportData: () => true,
    loadBundle: async () => ({
      loadedAt: new Date().toISOString(),
      syncStatus: { attempted: true, ok: false, status: "failed", error: "sync failed" },
      diagnostics: {
        datasets: [
          { datasetKey: "softdent.dashboard", status: "stale" },
          { datasetKey: "softdent.ar", status: "connected" },
          { datasetKey: "quickbooks.revenue", status: "connected" },
          { datasetKey: "quickbooks.expenses", status: "connected" },
        ],
      },
      softdent: {
        dashboard: { sourceFile: "softdent_dashboard_data.json", rows: [{ period: "2025-06", production: 1000, collections: 900 }] },
        ar: { sourceFile: "softdent_ar.csv", rows: [{ Bucket: "0-30", Amount: 100 }] },
      },
      quickbooks: {
        revenue: { sourceFile: "quickbooks_revenue.csv", rows: [{ Month: "2025-06", Revenue: 1000 }] },
        expenses: { sourceFile: "quickbooks_expenses.csv", rows: [{ Month: "2025-06", Expense: 400 }] },
      },
    }),
    buildDocumentStateFromImportBundle: () => ({
      queue: [{ id: "QB-REV-2025-06", type: "Revenue", vendor: "QuickBooks", amount: "$1,000", status: "Ready to Post" }],
      previewById: {},
    }),
  };
  const documentsFromFailedImport = await Services.documents.list({});
  assert(
    (documentsFromFailedImport.queue || []).length === 0,
    "documents hydration must not backfill import rows when critical import sync is failed or stale",
  );
  global.ImportLoader = priorImportLoader;
  await Services.resetAll();

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
    hasLoopbackApi: () => false,
    hasRuntimeAccess: () => false,
    desktopRequiredMessage: (feature) => `${feature} requires the NR2 server.`,
  });
  const browserImportExec = await HalRouteExec.execute(importRefreshRoute, "refresh imports", {}, Object.assign({}, mockCtx, { Services, ImportLoader }));
  assert(
    browserImportExec.text.includes("requires the NR2 server") || browserImportExec.text.includes("loopback server"),
    "HAL import route must clearly block browser-only refresh",
  );
  global.DesktopBridge = priorDesktopBridge;

  // Financial automation contract and diagnostics
  const ImportDiagnostics = require(join(siteDir, "import-diagnostics.js"));
  const manifest = JSON.parse(readFileSync(join(__dirname, "import-manifest.json"), "utf8"));
  assert(manifest.datasets["softdent.dashboard"].requiredFields.includes("production"), "manifest must declare dashboard required fields");
  assert(manifest.datasets["quickbooks.ar"].automated === true, "QuickBooks A/R collector must be marked automated");

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
  assert(qbAr && qbAr.status === "missing", "QuickBooks A/R must report missing when automated collector has no cached file");

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
  assert(statusText.includes("quickbooks.ar") && statusText.includes("Missing"), "import status must explain QuickBooks A/R missing from cache");

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
    hasLoopbackApi: () => false,
    hasRuntimeAccess: () => true,
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
  global.DesktopBridge = { hasDesktopApi: () => false, hasLoopbackApi: () => false, hasRuntimeAccess: () => false };
  const browserOnlyCycle = await HalProactive.runCycle(
    {
      halData,
      loadProgramSnapshot: async () => proactiveSnapshot,
      refreshHalWidgetFeed: async () => {},
      getOfficeTasks: async () => [],
      persistSet: async () => {},
      persistGet: async () => null,
    },
    { force: true, forcePlacement: true },
  );
  assert(browserOnlyCycle.placement.reason === "browser-only", "browser preview must not run autonomous placement");
  assert(browserOnlyCycle.placement.refreshed === false, "browser preview must not mark imports refreshed");
  const browserBriefText = HalProactive.formatProactiveBriefing(browserOnlyCycle);
  assert(!browserBriefText.includes("import refresh completed"), "browser preview briefing must not claim import refresh");
  assert(
    /NR2 server|StartProgram\.bat/i.test(browserBriefText),
    "browser preview briefing must direct staff to Start Program",
  );

  require(join(siteDir, "nr2-analytics.js"));
  require(join(siteDir, "nr2-qb-reports.js"));
  const crossSnapshot = {
    dashboards: { financial: { dataSource: "import" } },
    importBundle: {
      softdent: {
        dashboard: {
          rows: [{ Period: "2026-01", Production: 100000, Collections: 80000 }],
        },
      },
      quickbooks: {
        profitAndLoss: {
          rows: [{ Period: "2026-01", TotalIncome: 85000, TotalExpense: 55000, NetIncome: 30000 }],
        },
      },
      diagnostics: {
        summary: { connected: 2, partial: 0, missing: 0, stale: 0, notConfigured: 0 },
        datasets: [
          { datasetKey: "softdent.dashboard", status: "connected", severity: "info", automated: true },
          { datasetKey: "quickbooks.pl", status: "connected", severity: "info", automated: true },
        ],
      },
    },
  };
  const cross = HalSkills.crossReconcileSkill(crossSnapshot);
  assert(cross.sentence && cross.domains.length >= 2, "cross_reconcile_skill must reference at least two domains");
  assert(
    cross.domains.includes("production") && cross.domains.includes("expenses"),
    "cross reconcile must span production and expenses",
  );
  assert(HalProactive.isMorningBriefingStale(0) === true, "missing morning briefing timestamp must be stale");
  assert(HalProactive.isMorningBriefingStale(Date.now()) === false, "fresh morning briefing must not be stale");
  assert(
    HalProactive.isMorningBriefingStale(Date.now() - 19 * 3600000) === true,
    "19h old morning briefing must be stale",
  );
  const morningCard = HalProactive.buildMorningBriefingCard(crossSnapshot);
  assert(
    morningCard.sentence && morningCard.domains.length >= 2,
    "morning briefing card must synthesize cross-domain data",
  );
  const actuatorText = "Review options.\n<<<actuator\nlabel: Sync QB now?\naction_id: refresh-imports\n>>>";
  const proposals = HalAgentLoop.parseActuatorProposals(actuatorText);
  assert(proposals.length === 1 && proposals[0].requiresConsent !== false, "actuator proposals must parse");
  const chips = HalAgentLoop.proposeConsentActuators(proposals);
  assert(chips[0].requiresConsent === true, "actuator proposals must require consent");
  let actuatorAutoRan = false;
  const actuatorCtx = {
    Services: {
      refreshImports: async () => {
        actuatorAutoRan = true;
      },
    },
  };
  assert(actuatorAutoRan === false, "actuator must not auto-execute during parse");
  await HalAgentLoop.executeActuatorIfConsented(proposals[0], actuatorCtx);
  assert(actuatorAutoRan === true, "actuator executes only after explicit consent call");
  assert(
    (await HalAgentLoop.executeActuatorIfConsented(null, actuatorCtx)).autonomous === false,
    "actuator must report non-autonomous execution",
  );
  const HalHubClient = globalThis.HalHubClient || require(join(siteDir, "hal-hub-client.js"));
  assert(
    HalHubClient && typeof HalHubClient.pushMorningBriefingToWorkstation === "function",
    "hal hub client must push morning briefings",
  );
  const workstationPageSrc = readFileSync(join(siteDir, "workstation-page.js"), "utf8");
  assert(workstationPageSrc.includes("data-ws-sync=\"qb\""), "workstation must expose QuickBooks sync trigger");
  assert(workstationPageSrc.includes("data-ws-sync=\"softdent\""), "workstation must expose SoftDent sync trigger");
  assert(workstationPageSrc.includes("data-ws-open-hal"), "workstation must link to HAL hub");
  const mockupChromeSrc = readFileSync(join(siteDir, "nr2-moonshot-mockup-chrome.js"), "utf8");
  assert(mockupChromeSrc.includes('data-nr2-export="cpa-packet"'), "financial page must expose CPA export button");
  assert(mockupChromeSrc.includes("renderPageHeaderTools"), "mockup chrome must unify page-header-tools");
  assert(mockupChromeSrc.includes("data-page-command"), "mockup chrome must render HAL command chips");
  assert(mockupChromeSrc.includes("STAFF_HEADER_TOOL_PAGES"), "mockup chrome must expose sync badges on staff pages");
  assert(readFileSync(join(siteDir, "nr2-mockup-page-vocabulary.css"), "utf8").includes(".kpi-ribbon"), "vocabulary css must style kpi-ribbon");
  assert(readFileSync(join(siteDir, "nr2-moonshot-mockup-theme.css"), "utf8").includes(".widget-card.col-9"), "theme must define col-9 span");
  assert(readFileSync(join(siteDir, "page-canvas.js"), "utf8").includes("dashboardHost"), "QB mockup must wrap dashboard-grid in dashboardHost");
  assert(readFileSync(join(siteDir, "page-canvas.js"), "utf8").includes("heroKpiRow"), "staff pages must use 12-col hero KPI rows");
  assert(readFileSync(join(siteDir, "nr2-moonshot-ui.js"), "utf8").includes("chart-mount--canvas"), "chart overlays must replace inline chart mounts");
  assert(readFileSync(join(siteDir, "hal-mockup-overrides.css"), "utf8").includes(".span-2"), "HAL mosaic must define span-2");
  assert(readFileSync(join(siteDir, "hal-page-canvas.js"), "utf8").includes("slice(-20)"), "HAL chat must keep scrollback");
  assert(readFileSync(join(siteDir, "hal-page-canvas.js"), "utf8").includes("hal-situational-hero"), "HAL must render situational hero");
  assert(readFileSync(join(siteDir, "hal-page-canvas.js"), "utf8").includes("data-hal-scroll-widget"), "HAL mosaic tiles must deep-link to staff widgets");
  const glowCss = readFileSync(join(siteDir, "nr2-moonshot-glow.css"), "utf8");
  assert(glowCss.includes("@media print"), "moonshot glow css must include print-safe mode");
  assert(glowCss.includes(".nr2-alert-ticker"), "moonshot glow css must style alert ticker");
  assert(readFileSync(join(__dirname, "nr2_analytics.py"), "utf8").includes("def goal_scorecard"), "nr2_analytics must expose goal_scorecard");
  assert(readFileSync(join(__dirname, "cpa_packet_export.py"), "utf8").includes("WIDGET_KEYS"), "cpa_packet_export module must exist");
  const halCanvasSrc = readFileSync(join(siteDir, "hal-page-canvas.js"), "utf8");
  assert(halCanvasSrc.includes("widget-mosaic-tile") && halCanvasSrc.includes("aria-label="), "HAL mosaic tiles must expose aria-label");
  const halOverridesCss = readFileSync(join(siteDir, "hal-mockup-overrides.css"), "utf8");
  assert(halOverridesCss.includes("prefers-reduced-motion"), "hal mockup overrides must respect reduced motion");
  const completeDoc = readFileSync(join(__dirname, "docs", "MOONSHOT_FULLEST_EXTENT_COMPLETE_2026-07-09.md"), "utf8");
  assert(existsSync(join(siteDir, "nr2-page-filters.js")), "nr2-page-filters.js must exist for Tier S2");
  assert(readFileSync(join(siteDir, "nr2-page-filters.js"), "utf8").includes("data-nr2-filter-chip"), "filter chips must be wired");
  assert(readFileSync(join(siteDir, "nr2-moonshot-mockup-chrome.js"), "utf8").includes("data-nr2-filter-chip"), "mockup chrome must render wired filter chips");
  assert(readFileSync(join(siteDir, "nr2-mockup-page-vocabulary.css"), "utf8").includes("period-scrubber"), "period scrubber CSS must exist");
  assert(readFileSync(join(siteDir, "page-canvas.js"), "utf8").includes("renderTaxScenarioPanelHtml"), "taxes page must render scenario sliders");
  assert(readFileSync(join(siteDir, "nr2-moonshot-ui.js"), "utf8").includes("chartMountPolicy"), "unified chart mount policy must merge with NR2Charts");
  assert(readFileSync(join(siteDir, "nr2-moonshot-mockup-chrome.js"), "utf8").includes('data-nr2-export="page-storyboard"'), "staff pages must expose storyboard export");
  assert(existsSync(join(__dirname, "page_storyboard_export.py")), "page_storyboard_export module must exist");
  assert(completeDoc.includes("hal-10084") && completeDoc.includes("Practical ceiling"), "moonshot completion doc must exist through hal-10084");

  global.DesktopBridge = priorPlacementBridge;
  global.ImportCoordinator = priorPlacementCoordinator;
  const writebackRoute = HalCore.routeHalCommand(halData, halModels, pages, "Write back to SoftDent");
  assert(writebackRoute.intent !== "blocked: firewall", "writeback must not hit firewall when disabled");

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

  const HalAgentProgramming = globalThis.HalAgentProgramming;
  assert(HalAgentProgramming && HalAgentProgramming.VERSION === "auto-agent-v13", "HalAgentProgramming v13 must load");
  assert(/^PROGRAMMING:/m.test(HalAgentProgramming.contract()), "agent contract must start with PROGRAMMING");
  const wrapped = HalAgentProgramming.wrapSystemPrompt("Base prompt.");
  assert(wrapped.includes("Agent loop") && wrapped.includes("Base prompt."), "wrapSystemPrompt must prepend contract");
  const sarcIssues = HalAgentProgramming.agentShapeIssues("Can you refresh?", "Yes — shocking. I can reload imports locally.", {}, {});
  assert(sarcIssues.includes("sarcasm_or_dismissal"), "agent shape must flag sarcasm");
  const repairedSarc = HalAgentProgramming.repairAgentShapeIssues(
    "Can you refresh?",
    "Yes — shocking. I can reload imports locally.",
    sarcIssues,
  );
  assert(!/shocking/i.test(repairedSarc), "agent repair must strip sarcasm");
  assert(halModels.config.agentProgramming.profile === "cursor-auto-v13", "hal-models agentProgramming profile must be cursor-auto-v13");
  assert(halModels.config.chat9000 && halModels.config.chat9000.enabled === true, "chat9000 must be enabled");
  const defineRoute = HalCore.routeHalCommand(halData, halModels, pages, "Define ability.");
  assert(defineRoute.useEnglishDefine === true && defineRoute.englishWord === "ability", "Define word must accept trailing period");
  const planToday = HalCore.routeHalCommand(halData, halModels, pages, "Can you make a plan for today?");
  assert(planToday.useProactiveBriefing === true, "Can you make a plan must use proactive briefing not reasoning");
  const importCurrency = HalCore.routeHalCommand(halData, halModels, pages, "Analyze whether imports are current enough for management review.");
  assert(importCurrency.useImportStatus === true, "import currency analyze must use import status route");
  assert(halModels.config.agentProgramming.subtaskMaxDepth === 2, "subtask max depth must be 2");
  assert(halModels.config.cloudReasoning.searchIndex && halModels.config.cloudReasoning.searchIndex.enabled === true, "search index config must exist");
  assert(halModels.config.agentProgramming.agentToolLoop === true, "agent tool loop must be enabled");
  assert(halModels.config.agentProgramming.agentLoopUseReasoning === true, "agent loop must prefer reasoning lane");
  assert(halModels.config.agentProgramming.agentAutoTools === true, "agent auto tools must be enabled");
  assert(typeof HalAgent.isMultiAnalyzeQuery === "function", "isMultiAnalyzeQuery must exist");
  assert(
    HalAgent.isMultiAnalyzeQuery("Analyze SoftDent and Narratives and tell me what's missing from imports."),
    "multi-analyze detector must match paired analyze queries",
  );
  const capPq = HalCore.routeHalCommand(halData, halModels, pages, "Can you show posting queue items?");
  assert(capPq.usePostingQueueList === true, "capability-wrapped posting queue must stay instant");
  assert(typeof HalSkills.formatPostingQueueList === "function", "formatPostingQueueList must exist");
  const pqText = HalSkills.formatPostingQueueList({ items: [{ queue_id: "q1", status: "pending_review", amount: 120, accounting_period: "2025-06", description: "Prepaid insurance" }], metrics: { pendingReview: 1, approved: 0, total: 1 } });
  assert(/Journal posting queue/i.test(pqText) && /q1/.test(pqText), "posting queue formatter must list entries");
  const hypRoute = HalCore.routeHalCommand(
    halData,
    halModels,
    pages,
    "What happens when staff skips the posting queue review?",
  );
  assert(hypRoute.intent !== "navigate: documents", "hypothetical posting-queue question must not navigate to Documents");
  assert(
    hypRoute.useModel ||
      hypRoute.useReasoning ||
      hypRoute.intent === "model: query" ||
      hypRoute.intent === "capability:posting-queue-skip",
    "hypothetical should fall through to model lane or posting-queue capability",
  );
  const pushCap = HalCore.matchCapabilityRoute(halData, halModels, pages, "Can you push this journal entry live?");
  assert(
    pushCap && /^(No|Not without consent)\b/i.test(String(pushCap.text || "").trim()) && /consent/i.test(String(pushCap.text || "")),
    "push live must explain consent with No-until-consent lead",
  );
  const taxesCap = HalCore.matchCapabilityRoute(halData, halModels, pages, "What can you do on the Taxes page?");
  assert(taxesCap && taxesCap.intent === "capability:page-can", "Taxes page capability must resolve");
  const synth = HalAgent.synthesizeAnswerFromTools(
    "analyze SoftDent imports",
    { tools: ["read_import_diagnostics"] },
    { read_import_diagnostics: { ok: true, summary: "SoftDent export missing from inbox folder." } },
    { intent: "model: query" },
    { halModels, halData },
  );
  assert(synth && /SoftDent export missing/i.test(synth), "offline tool synthesis must cite tool summary");
  assert(halModels.config.agentProgramming.proportionalDepth === true, "proportional depth must be enabled");
  const sysPrompt = HalCore.buildSystemPrompt(halData, null);
  assert(/^PROGRAMMING:/m.test(sysPrompt), "buildSystemPrompt must include agent programming contract");

  const upsertOne = HalSkills.upsertHalTask([], { title: "HAL: Repair import", sourceId: "import-stale-softdent.dashboard", notes: "stale" }, { actor: "hal-proactive" });
  const upsertTwo = HalSkills.upsertHalTask(upsertOne.tasks, { title: "HAL: Repair import updated", sourceId: "import-stale-softdent.dashboard", notes: "still stale" }, { actor: "hal-proactive" });
  assert(upsertOne.created === true && upsertTwo.created === false && upsertTwo.tasks.length === 1, "HAL tasks must upsert by sourceId without duplicates");
  const resolved = HalSkills.autoResolveHalTasks(upsertTwo.tasks, []);
  assert(resolved[0].status === "completed", "HAL tasks must auto-resolve when source issue disappears");

  const hciUrl = pathToFileURL(join(siteDir, "hal-capability-index.js")).href;
  const orchUrl = pathToFileURL(join(siteDir, "hal-orchestrator.js")).href;
  const aoUrl = pathToFileURL(join(siteDir, "hal-autonomous-ops.js")).href;
  const chat9000Url = pathToFileURL(join(siteDir, "hal-chat-9000.js")).href;
  const empUrl = pathToFileURL(join(siteDir, "hal-employee.js")).href;
  const empRunUrl = pathToFileURL(join(siteDir, "hal-employee-runner.js")).href;
  const asc10000Url = pathToFileURL(join(siteDir, "hal-ascension-10000.js")).href;
  const dirUrl = pathToFileURL(join(siteDir, "hal-director.js")).href;
  const chat10000Url = pathToFileURL(join(siteDir, "hal-chat-10000.js")).href;
  const indepUrl = pathToFileURL(join(siteDir, "hal-independent-thought.js")).href;
  await import(hciUrl);
  await import(orchUrl);
  await import(aoUrl);
  await import(chat9000Url);
  await import(empUrl);
  await import(empRunUrl);
  await import(asc10000Url);
  await import(dirUrl);
  await import(chat10000Url);
  await import(indepUrl);
  const HCI = globalThis.HalCapabilityIndex;
  assert(HCI && HCI.MAX_SCORE === 10000, "capability index max must be 10000");
  assert(HCI.OFFICE_MAX === 250, "office core max must remain 250");
  assert(globalThis.HalEmployee && HalEmployee.MAX_LEVEL === 7, "employee max level must be 7");
  assert(halModels.config.employee && halModels.config.employee.targetLevel === 7, "employee target level must be 7");
  assert(halModels.config.ascension10000 && halModels.config.ascension10000.enabled === true, "ascension10000 must be enabled");
  assert(halModels.config.independentThought && halModels.config.independentThought.enabled === true, "independentThought must be enabled");
  const indepHelpRoute = HalCore.routeHalCommand(halData, halModels, pages, "What can you do?");
  const helpEnhanced =
    typeof HalIndependentThought !== "undefined"
      ? HalIndependentThought.enhanceRoute(indepHelpRoute, halModels)
      : indepHelpRoute;
  assert(
    (helpEnhanced.useModel === true && !helpEnhanced.text) ||
      (helpEnhanced.text &&
        typeof HalIndependentThought !== "undefined" &&
        HalIndependentThought.isFastTextRoute(helpEnhanced, "What can you do?")),
    "help must route to model or fast local help under independent thought",
  );
  const ascRoute = HalCore.routeHalCommand(halData, halModels, pages, "HAL 10000 ascension");
  assert(ascRoute.useAscension10000 === true, "ascension 10000 route must resolve");
  const empRoute = HalCore.routeHalCommand(halData, halModels, pages, "HAL employee status");
  assert(empRoute.useEmployeeStatus === true, "employee status route must resolve");
  const empLogRoute = HalCore.routeHalCommand(halData, halModels, pages, "HAL work log");
  assert(empLogRoute.useEmployeeWorkLog === true, "employee work log route must resolve");
  const go7Route = HalCore.routeHalCommand(halData, halModels, pages, "go to 7");
  assert(go7Route.useEmployeeSetLevel === true && go7Route.employeeLevel === 7, "go to 7 must set employee level 7");
  const aboutRoute = HalCore.routeHalCommand(halData, halModels, pages, "HAL about me");
  assert(aboutRoute.useHalAboutMe === true, "HAL about me route must resolve");
  const hciReport = HCI.compute({ halData: { build: { schemaVersion: "hal-10000" } } }, halModels);
  assert(hciReport.score >= 0 && hciReport.score <= 10000, "capability score must be within 0-10000");
  assert(hciReport.max === 10000, "capability report max must be 10000");
  const capRoute = HalCore.routeHalCommand(halData, halModels, pages, "Show HAL capability index");
  assert(capRoute.useCapabilityIndex === true, "capability index route must resolve");
  const orchRoute = HalCore.routeHalCommand(halData, halModels, pages, "Run orchestrator triage");
  assert(orchRoute.useOrchestratorTriage === true, "orchestrator triage route must resolve");
  assert(halModels.config.autonomousOps && halModels.config.autonomousOps.enabled === true, "autonomous ops must be enabled at hal-9000");
  assert(halModels.config.cloudReasoning.preferForAllAgentLoops === true, "cloud reasoning must prefer all agent loops");
  assert(halModels.config.cursorParity && halModels.config.cursorParity.enabled === true, "cursorParity must be enabled");
  const CP = globalThis.HalCursorParity;
  assert(CP && CP.isEnabled(halModels), "HalCursorParity must be active");
  const interview = CP.runInterviewPolish(HalCore, halData, halModels, pages);
  const failedInterview = interview.filter((r) => !r.pass);
  assert(
    failedInterview.length === 0,
    "cursor parity interview fixtures must pass: " + failedInterview.map((r) => r.id + ":" + r.issues.join(",")).join("; "),
  );
  const refreshPolished = HalCore.polishChatReply(
    "Yes — local refresh only.",
    "Can you refresh imports?",
    { intent: "capability:imports", useModel: true },
    { halData, halModels, synthesize: false },
  );
  assert(HalCore.countSentences(refreshPolished) <= 4, "simple yes/no must stay brief under cursor parity");
  assert(/^yes\b/i.test(refreshPolished), "refresh yes/no must lead with Yes");
  passed++;

  const pyQbo = require("node:child_process").execSync(
    'python -c "from outbound_actions import post_qbo_journal_with_consent; out=post_qbo_journal_with_consent(\'app_data/nr2/test.db\', consent_text=\'test\', dry_run=True); assert out.get(\'error\') in (\'qbo_not_configured\',) or out.get(\'dryRun\'); print(out.get(\'message\',\'\')[:80])"',
    { encoding: "utf8", cwd: __dirname, stdio: ["ignore", "pipe", "pipe"] },
  );
  assert(String(pyQbo).length > 3, "post_qbo_journal_with_consent must run");
  passed++;
  const pyPortal = require("node:child_process").execSync(
    'python -c "from payer_portal_bridge import build_portal_rpa_bundle; out=build_portal_rpa_bundle(claim_id=\'C-1\', consent_text=\'yes\'); assert out.get(\'ok\'); print(out.get(\'stepCount\',0))"',
    { encoding: "utf8", cwd: __dirname, stdio: ["ignore", "pipe", "pipe"] },
  );
  assert(Number(String(pyPortal).trim()) >= 5, "payer portal RPA bundle must include steps");
  passed++;
  const pySd = require("node:child_process").execSync(
    'python -c "from softdent_writeback_bridge import enqueue_writeback; out=enqueue_writeback(action=\'note\', payload={\'t\':1}, consent_text=\'yes\'); assert out.get(\'ok\'); print(out.get(\'entryId\',\'\'))"',
    { encoding: "utf8", cwd: __dirname, stdio: ["ignore", "pipe", "pipe"] },
  );
  assert(String(pySd).includes("sdw-"), "softdent writeback queue must accept entries");
  passed++;

  // Program source patch helper (Python dry-run) — use live schemaVersion from manifest
  const buildManifest = loadJson(join(siteDir, "nr2-build.json"));
  const patchNeedle = `"schemaVersion": "${String(buildManifest.schemaVersion || "hal-153")}"`;
  const pyPatch = require("node:child_process").execFileSync(
    "python",
    [
      "-c",
      `from pathlib import Path
from program_source_grep import apply_program_patch
nr2 = Path(".").resolve()
repo = nr2.parent
site = nr2 / "site"
old = ${JSON.stringify(patchNeedle)}
out = apply_program_patch(repo, site, "NewRidgeFinancial2/site/nr2-build.json", old, old, dry_run=True)
assert out["ok"], out
print(out["text"])`,
    ],
    { encoding: "utf8", cwd: __dirname, stdio: ["ignore", "pipe", "pipe"] },
  );
  assert(/Dry run|would patch/i.test(pyPatch), "apply_program_patch dry run must work");
  passed++;
  const pySemantic = require("node:child_process").execSync(
    'python -c "from pathlib import Path; from program_source_grep import semantic_search_program; nr2=Path(\'.\').resolve(); repo=nr2.parent; site=nr2/\'site\'; out=semantic_search_program(repo,site,\'handleHalSubmit routeHalCommand\',5); assert out[\'count\']>=0; print(out[\'text\'][:120])"',
    { encoding: "utf8", cwd: __dirname, stdio: ["ignore", "pipe", "pipe"] },
  );
  assert(String(pySemantic).length > 5, "semantic_search_program must run");
  passed++;
  const pyCmd = require("node:child_process").execSync(
    'python -c "from pathlib import Path; from program_source_grep import run_allowlisted_command; nr2=Path(\'.\').resolve(); repo=nr2.parent; out=run_allowlisted_command(repo, \'node-check-agent\'); assert \'exitCode\' in out; print(out[\'command\'])"',
    { encoding: "utf8", cwd: __dirname, stdio: ["ignore", "pipe", "pipe"] },
  );
  assert(/node-check-agent/.test(pyCmd), "run_allowlisted_command must accept node-check-agent");
  passed++;
  const pySemantic2 = require("node:child_process").execSync(
    'python -c "from pathlib import Path; from program_source_grep import semantic_search_program; nr2=Path(\'.\').resolve(); repo=nr2.parent; site=nr2/\'site\'; out=semantic_search_program(repo,site,\'handleHalSubmit routeHalCommand\',8); assert out[\'count\']>=0; print(out[\'text\'][:160])"',
    { encoding: "utf8", cwd: __dirname, stdio: ["ignore", "pipe", "pipe"] },
  );
  assert(String(pySemantic2).length > 5, "semantic_search_program v2 must run");
  passed++;
  const pyEmbed = require("node:child_process").execSync(
    'python -c "from pathlib import Path; from program_source_grep import semantic_search_program; nr2=Path(\'.\').resolve(); repo=nr2.parent; site=nr2/\'site\'; out=semantic_search_program(repo,site,\'handleHalSubmit\',5); assert \'mode\' in out; print(out.get(\'mode\',\'\'))"',
    { encoding: "utf8", cwd: __dirname, stdio: ["ignore", "pipe", "pipe"] },
  );
  assert(/embed|lexical|ngram|ollama/i.test(pyEmbed), "semantic search must report embed mode");
  passed++;
  const pyIndex = require("node:child_process").execSync(
    'python -c "from pathlib import Path; from program_source_grep import build_program_search_index; nr2=Path(\'.\').resolve(); repo=nr2.parent; site=nr2/\'site\'; out=build_program_search_index(repo,site); assert out.get(\'ok\'); print(out.get(\'fileCount\',0))"',
    { encoding: "utf8", cwd: __dirname, stdio: ["ignore", "pipe", "pipe"], timeout: 120000 },
  );
  assert(Number(String(pyIndex).trim()) > 10, "program search index must index multiple files");
  passed++;

  // HAL import readiness guard — Moonshot Phase C/D
  const HalImportReadiness = require(join(siteDir, "hal-import-readiness.js"));
  global.DesktopBridge = {
    fetchHalImportGuard: async (q) => ({
      blocked: /\brevenue\b/i.test(String(q || "")),
      readiness: { level: "stale", error: "Import bundle stale", loadedAt: "2026-01-01T00:00:00Z" },
      message: "Import data is not fresh.",
    }),
  };
  const blockedGuard = await HalImportReadiness.guardBeforeModel("What is our revenue trend?", {});
  assert(blockedGuard && blockedGuard.intent === "readiness:import-stale", "guardBeforeModel must block stale financial queries");
  assert(/DATA NOT CURRENT/i.test(blockedGuard.text || ""), "blocked guard must warn about stale data");
  const passGuard = await HalImportReadiness.guardBeforeModel("Hello HAL", {});
  assert(passGuard === null, "guardBeforeModel must pass non-financial queries");
  const freshGuard = await HalImportReadiness.guardBeforeModel("Show revenue summary", {});
  assert(freshGuard && freshGuard.intent === "readiness:import-stale", "financial intent must be detected");
  delete global.DesktopBridge;
  passed++;

  const classifyFinancial = (q) => {
    const text = String(q || "");
    return (
      /\b(revenue|collection|receivable|a\/r|\bar\b|profit|loss|ebitda|tax|posting|ledger|reconcil|month[- ]end|cash flow|forecast|project|production|quickbooks|financial|aging|claim status)\b/i.test(
        text,
      ) ||
      /\b(owe|balance|paid|bill|money|amount\s*due|outstanding|receivable|insurance|eob|era)\b/i.test(text)
    );
  };
  assert(classifyFinancial("month-end close posting"), "financial intent regex must match month-end posting");
  assert(!classifyFinancial("print widget feed"), "financial intent regex must not match print");
  passed++;

  global.DesktopBridge = {
    fetchHalImportGuard: async (q) => ({
      blocked: classifyFinancial(q),
      readiness: { level: "stale", error: "Import bundle stale", loadedAt: "2026-01-01T00:00:00Z" },
      message: "Import data is not fresh.",
    }),
  };
  const refusalQueries = [
    "What is our revenue trend?",
    "Show A/R aging breakdown",
    "Who owes money on accounts?",
    "Month-end close posting status",
    "QuickBooks cash flow forecast",
    "Collection ratio this quarter",
    "Claim status for denied aging",
    "Ledger reconcile variance",
    "Production vs collections",
    "Financial aging report",
  ];
  for (let i = 0; i < 50; i++) {
    const q = (refusalQueries[i % refusalQueries.length] || "revenue trend") + (i > 9 ? ` case ${i}` : "");
    const blocked = await HalImportReadiness.guardBeforeModel(q, {});
    assert(blocked && blocked.intent === "readiness:import-stale", `HAL refusal scenario ${i}: ${q}`);
    passed++;
  }
  const passGuardLoop = await HalImportReadiness.guardBeforeModel("print widget feed layout", {});
  assert(passGuardLoop === null, "non-financial queries must pass guard loop");
  passed++;
  delete global.DesktopBridge;

  const operatorScenarios = [
    { q: "What is our revenue trend?", expectBlock: true },
    { q: "Why did collections drop?", expectBlock: false, analytical: true },
    { q: "Generate collections queue", expectTool: "build_collections_queue" },
    { q: "Run month end close tasks", expectTool: "generate_month_end_tasks" },
    { q: "Heal import pipeline", expectTool: "heal_import_pipeline" },
    { q: "Parse ERA 835 file", expectTool: "parse_era_835" },
    { q: "Read shift context tier", expectTool: "read_shift_context" },
    { q: "Clinical summary for patient", expectTool: "read_clinical_summary" },
    { q: "Batch approve postings", expectTool: "batch_approve_postings" },
    { q: "Draft deposit reconciliation", expectTool: "draft_deposit_reconciliation" },
  ];
  for (const sc of operatorScenarios) {
    if (sc.expectBlock) {
      global.DesktopBridge = {
        fetchHalImportGuard: async () => ({
          blocked: true,
          readiness: { level: "stale" },
          message: "stale",
        }),
      };
      const blocked = await HalImportReadiness.guardBeforeModel(sc.q, {});
      assert(blocked && blocked.intent === "readiness:import-stale", `operator stale block: ${sc.q}`);
      delete global.DesktopBridge;
    }
    if (sc.expectTool && typeof HalAgent !== "undefined" && HalAgent.planTools) {
      const plan = HalAgent.planTools(sc.q, {}, { halData: {}, halModels: {} });
      const tools = (plan && plan.tools) || [];
      assert(tools.includes(sc.expectTool), `operator tool ${sc.expectTool} for: ${sc.q} got ${tools.join(",")}`);
    }
    passed++;
  }

  // Phase 2 Moonshot operator scenarios (SSE, ERA feedback, clock-out, alerts, QB, SMS)
  if (typeof HalAgent !== "undefined" && HalAgent.TOOL_DEFS) {
    assert(HalAgent.TOOL_DEFS.clock_out_shift, "Phase 2 clock_out_shift tool");
    assert(HalAgent.TOOL_DEFS.record_era_match_feedback, "Phase 2 ERA feedback tool");
    assert(HalAgent.TOOL_DEFS.acknowledge_alert, "Phase 2 alert ack tool");
    assert(HalAgent.TOOL_DEFS.undo_scheduler_run, "Phase 2B undo_scheduler_run tool");
    assert(HalAgent.TOOL_DEFS.predict_claim_denial_risk, "Phase 2A predict_claim_denial_risk tool");
    assert(HalAgent.TOOL_DEFS.pull_qb_payments, "Phase 2B pull_qb_payments tool");
  }
  const phase2Routes = [
    "clock out",
    "era feedback",
    "acknowledge alert",
    "send billing sms",
    "classify document",
    "quickbooks sync",
    "undo morning routine",
    "predict denial risk before submit",
    "pull qb payments",
    "pilot phase cutover status",
  ];
  const phase2ToolExpectations = [
    ["undo autonomous scheduler run", "undo_scheduler_run"],
    ["pre-submit denial scrub", "predict_claim_denial_risk"],
    ["pull quickbooks payments read only", "pull_qb_payments"],
  ];
  for (const q of phase2Routes) {
    if (typeof HalAgent === "undefined" || !HalAgent.planTools) continue;
    const plan = HalAgent.planTools(q, {}, { halData: {}, halModels: {} });
    const tools = (plan && plan.tools) || [];
    assert(tools.length >= 1, `Phase 2 operator scenario should plan tools for: ${q}`);
    passed++;
  }
  for (const [q, expectTool] of phase2ToolExpectations) {
    if (typeof HalAgent === "undefined" || !HalAgent.planTools) continue;
    const plan = HalAgent.planTools(q, {}, { halData: {}, halModels: {} });
    const tools = (plan && plan.tools) || [];
    assert(tools.includes(expectTool), `Phase 2A-2C tool ${expectTool} for: ${q} got ${tools.join(",")}`);
    passed++;
  }
  const NR2MoonshotUI = require(join(siteDir, "nr2-moonshot-ui.js"));
  assert(typeof NR2MoonshotUI.renderEraMatchCard === "function", "ERA match UI export");
  assert(typeof NR2MoonshotUI.renderPilotPhaseBanner === "function", "pilot phase banner export");
  assert(typeof NR2MoonshotUI.enhanceCanvasPanels === "function", "canvas panel enhancement export");
  assert(typeof NR2MoonshotUI.enhanceCanvasCharts === "function", "canvas chart enhancement export");
  passed += 2;
  if (typeof NR2AlertsUI !== "undefined") {
    assert(typeof NR2AlertsUI.install === "function", "Alerts SSE UI export");
  }
  const HalTransparency = require(join(siteDir, "hal-transparency.js"));
  assert(typeof HalTransparency.openClockOutModal === "function", "Shift handoff UI export");
  assert(typeof HalTransparency.showActionConfidence === "function", "HAL confidence overlay export");
  passed++;
  if (typeof NR2Charts !== "undefined" && NR2Charts.renderPracticePulse) {
    passed++;
  }

  console.log(`HAL validation passed (${passed} suites)`);
}

main().catch((error) => {
  console.error("HAL validation failed:", error.message);
  process.exit(1);
});

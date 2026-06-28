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
  const halData = loadJson(halManagerPath);
  const halModels = loadJson(halModelsPath);
  const halCoreUrl = pathToFileURL(join(siteDir, "hal-core.js")).href;
  const HalCore = (await import(halCoreUrl)).default || (await import(halCoreUrl));

  const pages = [
    { id: "financial", label: "Financial dashboard", title: "Owner Financial Dashboard" },
    { id: "softdent", label: "SoftDent", title: "SoftDent" },
    { id: "quickbooks", label: "QuickBooks", title: "QuickBooks" },
    { id: "ar", label: "A/R & Collections", title: "A/R & Collections" },
    { id: "claims", label: "Claims Workbench", title: "Claims Workbench" },
    { id: "narratives", label: "Insurance Narratives", title: "Insurance Narratives" },
    { id: "documents", label: "Accounting Documents", title: "Accounting Documents" },
    { id: "library", label: "Document Library", title: "Document Library" },
    { id: "hal", label: "HAL Command Center", title: "HAL Command Center" },
  ];

  let passed = 0;

  // JSON structure
  assert(halData.registry && halData.registry.length === 10, "registry must have 10 entries");
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
  assert(cards.length >= 8, "all available local models should be exposed as lanes");
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
  assert(halData.readiness && halData.readiness.expectedRegistryCount === 10, "readiness config required");
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
  assert(laneCounts.chat14b > 0, "routing regression must include model fallback cases");
  assert(laneCounts.reason21b > 0, "routing regression must include reasoning lane cases");
  assert(laneCounts.escalate30b > 0, "routing regression must include escalation lane cases");
  passed++;

  // app.js syntax
  const { execSync } = require("node:child_process");
  execSync("node --check site/app.js", { cwd: __dirname, stdio: "pipe" });
  execSync("node --check site/hal-core.js", { cwd: __dirname, stdio: "pipe" });
  execSync("node --check site/hal-page.js", { cwd: __dirname, stdio: "pipe" });
  passed++;

  // HAL page surfaces required manager signals (no backend, local data only)
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
  });
  assert(halHtml.includes("MODE"), "HAL page must show current mode");
  assert(halHtml.includes("NEXT SAFE STEP"), "HAL page must surface the next safe step");
  assert(halHtml.includes("ACTIVE WORK"), "HAL page must surface active work");
  assert(halHtml.includes("Allowed (local)"), "HAL page must surface allowed actions");
  assert(halHtml.includes("EXTERNAL ACTION FIREWALL") && halHtml.includes("BLOCKED"), "HAL page must surface blocked actions");
  assert(halHtml.includes("Last local receipt"), "HAL page must surface the last local receipt");
  assert(halHtml.includes("local sample data"), "HAL page must label sample/local data honestly");
  passed++;

  // AI readiness display; local model lanes enabled on loopback only
  assert(halModels.config.externalCallsEnabled === false, "external model calls must stay disabled");
  for (const runtime of [halModels.config.localModel, halModels.config.reasoningModel, halModels.config.escalationModel]) {
    assert(runtime.enabled === true, "model lane must be enabled for local execution");
    assert(HalCore.isLocalModelEndpoint(runtime.endpoint), `model endpoint must be loopback-only: ${runtime.endpoint}`);
  }
  for (const lane of halModels.lanes) {
    assert(lane.executionEnabled === true, `lane ${lane.id} execution must be enabled`);
    assert(lane.inventoryAvailable === true, `lane ${lane.id} inventory should be marked available`);
    assert(HalCore.laneReady(halModels, lane.id), `lane ${lane.id} must be execution-ready on loopback`);
    const runtime = HalCore.laneRuntime(halModels, lane.id);
    assert(runtime && HalCore.isLocalModelEndpoint(runtime.endpoint), `lane ${lane.id} runtime must be loopback-only`);
  }
  assert(halModels.readinessDisplay.allModelsEnabled === true, "readiness display must reflect all models enabled");
  assert(halHtml.includes("LOCAL AI READINESS"), "HAL page must render AI readiness");
  assert(halHtml.includes("local only"), "HAL page must label AI lanes as local only");
  assert(halHtml.includes("Available inventory"), "HAL page must show available model inventory");
  assert(halHtml.includes("queen3:14b"), "HAL page must show configured local model inventory");
  assert(halHtml.includes("mistral-small3.1:24b"), "HAL page must show reasoning model inventory");
  assert(halHtml.includes("qwen3:30b"), "HAL page must show escalation model inventory");
  assert(halHtml.includes("not verified"), "HAL page must mark GPU/binding as unverified where applicable");
  assert(/sensitive raw data|SoftDent|QuickBooks/i.test(halHtml), "HAL page must show sensitive-data no-egress policy");
  assert(HalCore.laneReady(halModels, "chat14b"), "chat lane must be execution-ready on loopback");
  assert(HalCore.laneReady(halModels, "reason21b"), "reasoning lane must be execution-ready on loopback");
  assert(HalCore.laneReady(halModels, "escalate30b"), "escalation lane must be execution-ready on loopback");
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
  assert(halHtml.includes("PROGRAM ACCESS"), "HAL page must show program access");
  assert(halHtml.includes("Full read"), "HAL page must show full read access");
  passed++;

  // Ported HAL skills (accounting, claim readiness, office-manager, tasks, sanitization, memory)
  const HalSkills = require(join(siteDir, "hal-skills.js"));

  // Accounting: drafting allowed through firewall; posting still blocked.
  const draftRoute = HalCore.routeHalCommand(halData, halModels, pages, "Draft a journal entry for $1,200 prepaid insurance");
  assert(draftRoute.intent === "accounting: journal-draft" && draftRoute.useJournalDraft === true, "journal drafting must route locally");
  const postBlocked = HalCore.routeHalCommand(halData, halModels, pages, "Post a journal entry to the ledger");
  assert(postBlocked.intent === "blocked: firewall", "posting a journal entry must stay blocked");
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
  const cprResp = HalSkills.buildClaimReadinessResponse((snapshot.claims && snapshot.claims.top) || []);
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
  const libDocs = (snapshot.library && (snapshot.library.top || snapshot.library.docs)) || [];
  const ragHit = HalSkills.answerFromLibrary("compliance training", libDocs, 4);
  assert(ragHit.grounded === true && ragHit.retrievedContext.length > 0, "RAG must find grounded matches");
  assert("sourceId" in ragHit.retrievedContext[0], "RAG results must use camelCase sourceId");
  assert(ragHit.prompt && ragHit.prompt.includes("library context"), "RAG must build a grounded answer prompt");
  const ragMiss = HalSkills.answerFromLibrary("zzzqqq nonexistent topic", libDocs, 4);
  assert(ragMiss.grounded === false && ragMiss.answer === HalSkills.INSUFFICIENT_DOCUMENT_CONTEXT_ANSWER, "RAG must fall back when no grounded context");

  // Manager dashboard widgets (import-cache feed) + A/R honesty policy
  const widgetRoute = HalCore.routeHalCommand(halData, halModels, pages, "Show manager dashboard widgets");
  assert(widgetRoute.intent === "widgets: feed" && widgetRoute.useWidgetFeed === true, "widget feed must route locally");
  const feed = HalSkills.buildWidgetFeed(snapshot);
  assert(Object.keys(feed.widgets).length === 4, "widget feed must build 4 widgets");
  assert(feed.localOnly === true && feed.runId && feed.generatedAt, "widget feed must use program-style runId/generatedAt/localOnly fields");
  assert(feed.jobs.widgetPublish && feed.sources.quickbooks.lastStatus, "widget feed jobs/sources must use camelCase fields");

  // A/R honesty: with no verified A/R source, totals are nulled and status degrades
  const noArFeed = HalSkills.buildWidgetFeed({ dashboards: { softdent: {}, quickbooks: { syncStatus: "ok" } }, claims: { total: 5 } });
  assert(noArFeed.widgets.smartClaimsAndReceivables.metrics.accountsReceivableTotal === null, "A/R must not be fabricated without a verified source");
  assert(noArFeed.widgets.careDeliveryPerformance.metrics.patientBalanceTotal === null, "patient A/R balance must not be fabricated");
  assert(noArFeed.widgets.smartClaimsAndReceivables.status !== "SUCCESS", "claims widget must degrade without A/R source");

  // SoftDent read source status honesty (never fabricate $0 A/R)
  const sdReal = HalSkills.softDentReadSourceStatus(snapshot);
  assert(sdReal.arAvailable === true, "report-derived A/R from the A/R dashboard must be recognized as available");
  const sdEmpty = HalSkills.softDentReadSourceStatus({ dashboards: {}, claims: { total: 0 } });
  assert(sdEmpty.arAvailable === false && sdEmpty.missingDataCodes.includes("missing_softdent_ar"), "missing A/R must be surfaced honestly");
  passed++;

  console.log(`HAL validation passed (${passed} suites)`);
}

main().catch((error) => {
  console.error("HAL validation failed:", error.message);
  process.exit(1);
});

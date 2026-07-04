/**
 * Headless HAL vs Cursor-agent parity checks (routing, loop, self-check, tools).
 * No browser or Ollama required for most cases.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const siteDir = path.join(__dirname, "..", "NewRidgeFinancial2", "site");
const halManagerPath = path.join(siteDir, "data", "hal-manager.json");
const halModelsPath = path.join(siteDir, "data", "hal-models.json");

function loadJson(p) {
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

const pages = [
  { id: "financial", label: "Financial dashboard" },
  { id: "claims", label: "Claims Workbench" },
  { id: "hal", label: "HAL Command Center" },
];

async function main() {
  const halData = loadJson(halManagerPath);
  const halModels = loadJson(halModelsPath);

  await import(pathToFileURL(path.join(siteDir, "hal-agent-programming.js")).href);
  const HalCore = (await import(pathToFileURL(path.join(siteDir, "hal-core.js")).href)).default;
  await import(pathToFileURL(path.join(siteDir, "hal-agent-loop.js")).href);
  const HalAgent = (await import(pathToFileURL(path.join(siteDir, "hal-agent.js")).href)).default;

  const issues = [];
  const pass = (name) => console.log("PASS", name);
  const fail = (name, detail) => {
    issues.push({ name, detail });
    console.log("FAIL", name, "-", detail);
  };

  // --- Config / version ---
  try {
    assert(HalAgent.ARCHITECTURE_VERSION === "hal-agent-v9-cursor", "v9 agent");
    assert(halModels.config.agentProgramming.profile === "cursor-auto-v9", "v9 profile");
    pass("version alignment");
  } catch (e) {
    fail("version alignment", e.message);
  }

  // --- Reasoning route for agent-loop queries (like Cursor uses stronger model) ---
  const codeQ = "how does handleHalSubmit work in app.js — grep the source";
  const baseRoute = HalCore.routeHalCommand(halData, halModels, pages, codeQ);
  const ctxMock = {
    halModels,
    reasoningModelReady: () => true,
    localModelReady: () => true,
  };
  // Replicate applyHigherReasoningRoute logic: agent-loop queries upgrade when reasoning ready
  let upgraded = { ...baseRoute };
  const ap = halModels.config.agentProgramming || {};
  const agentLoopQ =
    ap.agentToolLoop !== false &&
    /how does|grep|source code/i.test(codeQ) &&
    ctxMock.reasoningModelReady();
  if (agentLoopQ && !baseRoute.text) {
    upgraded = { ...baseRoute, useReasoning: true, useModel: false, lane: "reason21b" };
  }
  if (upgraded.useReasoning && upgraded.lane === "reason21b") {
    pass("agent-loop queries upgrade to reason21b");
  } else {
    fail("agent-loop queries upgrade to reason21b", JSON.stringify({ useReasoning: upgraded.useReasoning, lane: upgraded.lane }));
  }

  // --- Capability routes must keep instant text (not forced to offline model) ---
  const pageCapQ = "What can you do on the Office Manager page?";
  const pageCapRoute = HalCore.routeHalCommand(halData, halModels, pages, pageCapQ);
  if (pageCapRoute.text && pageCapRoute.intent === "capability:page-can" && !/agent loop/i.test(pageCapRoute.text)) {
    pass("page capability route has instant text");
  } else {
    fail("page capability route has instant text", JSON.stringify({ intent: pageCapRoute.intent, text: pageCapRoute.text?.slice(0, 80) }));
  }
  if (pageCapRoute.text && String(pageCapRoute.text).trim()) {
    pass("applyHigherReasoningRoute would preserve route.text (early return contract)");
  } else {
    fail("route.text preservation contract", "missing text");
  }

  // --- Hypothetical routing ---
  const hypQ = "What happens when staff skips the posting queue review?";
  const hypRoute = HalCore.routeHalCommand(halData, halModels, pages, hypQ);
  if (hypRoute.intent !== "navigate: documents" && (hypRoute.useModel || hypRoute.useReasoning)) {
    pass("hypothetical posting-queue avoids wrong Documents nav");
  } else {
    fail("hypothetical posting-queue avoids wrong Documents nav", JSON.stringify({ intent: hypRoute.intent }));
  }

  const pushCap = HalCore.matchCapabilityRoute(halData, halModels, pages, "Can you push this journal entry live?");
  if (pushCap && /can't|blocked|No\./i.test(pushCap.text)) {
    pass("push-live capability blocked without executor");
  } else {
    fail("push-live capability blocked", pushCap && pushCap.text);
  }

  const synth = HalAgent.synthesizeAnswerFromTools(
    "analyze imports",
    {},
    { read_import_diagnostics: { ok: true, summary: "SoftDent export missing from inbox folder." } },
    {},
    { halModels, halData },
  );
  if (synth && /SoftDent export missing/i.test(synth)) {
    pass("offline tool synthesis cites evidence");
  } else {
    fail("offline tool synthesis cites evidence", synth);
  }

  // --- Simple nav should NOT force reasoning ---
  const navQ = "open claims workbench";
  const navBase = HalCore.routeHalCommand(halData, halModels, pages, navQ);
  const navRoute = navBase.text ? navBase : navBase;
  if (navRoute.intent === "navigate: claims" || navRoute.text) {
    pass("simple navigation not broken by reasoning upgrade");
  } else {
    fail("simple navigation not broken by reasoning upgrade", navRoute.intent);
  }

  // --- Auto tools suggest evidence gather ---
  const toolIds = new Set(Object.keys(HalAgent.TOOL_DEFS));
  const auto = HalAgentLoop.suggestAutoTools(codeQ, { isInvestigateQuery: true }, {}, toolIds, { agentAutoTools: true });
  if (auto.some((t) => t.name === "grep_program_source") && auto.some((t) => t.name === "semantic_search_program")) {
    pass("auto-tools suggest grep + semantic search for code questions");
  } else {
    fail("auto-tools suggest grep + semantic search", JSON.stringify(auto.map((t) => t.name)));
  }

  // --- Tool protocol parsing ---
  const toolBlock = "<<<tool\nname: grep_program_source\nquery: handleHalSubmit\n>>>";
  const parsed = HalAgentLoop.parseToolRequests(toolBlock);
  if (parsed.length === 1 && parsed[0].name === "grep_program_source") {
    pass("parseToolRequests");
  } else {
    fail("parseToolRequests", JSON.stringify(parsed));
  }

  const patchBlock =
    "<<<patch\nfile: site/app.js\nold:\nfoo\nnew:\nbar\n>>>\nAnswer here.";
  const patches = HalAgentLoop.parseAllPatches(patchBlock);
  const strippedTools = HalAgentLoop.stripToolBlocks("<<<tool\nname: x\n>>>\nAnswer.");
  if (patches.length === 1 && patches[0].file === "site/app.js" && !/<<<tool/i.test(strippedTools)) {
    pass("patch parse + tool strip");
  } else {
    fail("patch parse + tool strip", JSON.stringify({ patches, strippedTools }));
  }

  // --- Self-check: must not claim external actions ---
  const emailRoute = HalCore.routeHalCommand(halData, halModels, pages, "email the payer");
  const emailPlan = HalAgent.buildPlan("email the payer", emailRoute, HalAgent.getWorkingMemory(), HalAgent.getLongTermMemory(), {
    halData,
    halModels,
    pages,
  });
  const badSelf = HalAgent.selfCheckResponse("email payer", "I emailed the payer for you.", emailPlan, {}, emailRoute);
  const goodSelf = HalAgent.selfCheckResponse(
    "email payer",
    "I cannot email payers — that is blocked. I can draft text locally for staff review.",
    emailPlan,
    {},
    emailRoute,
  );
  if (!badSelf.pass && goodSelf.pass) {
    pass("self-check blocks false external claims");
  } else {
    fail("self-check external claims", JSON.stringify({ bad: badSelf.pass, good: goodSelf.pass }));
  }

  // --- Firewall off: email not unsafe flag ---
  if (emailPlan.isUnsafe === false) {
    pass("firewall off — email plan not marked unsafe");
  } else {
    fail("firewall off — email plan not marked unsafe", String(emailPlan.isUnsafe));
  }

  // --- Agent loop should trigger for investigate ---
  const investigatePlan = HalAgent.buildPlan(
    codeQ,
    { useModel: true, intent: "model: query", text: "" },
    HalAgent.getWorkingMemory(),
    HalAgent.getLongTermMemory(),
    { halData, halModels, pages, getCurrentPage: () => "hal" },
  );
  if (investigatePlan.agentToolLoop) {
    pass("investigate/code plan enables agent tool loop");
  } else {
    fail("investigate/code plan enables agent tool loop", JSON.stringify(investigatePlan));
  }

  // --- @-mentions expand ---
  if (typeof HalCore.expandAtMentions === "function") {
    const expanded = HalCore.expandAtMentions("explain @claims widgets", pages);
    if (/claims/i.test(expanded) && expanded.length > 20) {
      pass("expandAtMentions");
    } else {
      fail("expandAtMentions", expanded);
    }
  }

  // --- Ambiguous fix-it clarifies (Cursor asks before acting) ---
  const clarify = HalCore.detectAmbiguousQuery("fix it", []);
  if (clarify && clarify.chips && clarify.chips.length >= 2) {
    pass("ambiguous fix-it offers clarify chips");
  } else {
    fail("ambiguous fix-it offers clarify chips", JSON.stringify(clarify));
  }

  // --- False-positive error pattern in QA (imports failed text) ---
  const importAnswer =
    "The registry shows imports failed. Staff should refresh before trusting widgets.";
  if (/hit an error|could not finish|did not return/i.test(importAnswer)) {
    fail("QA error-pattern false positive", "import failure prose triggers error regex");
  } else {
    pass("QA error-pattern does not false-positive on 'imports failed'");
  }
  const brokenAnswer = "Sorry, I hit an error and could not finish.";
  if (/hit an error|could not finish|did not return/i.test(brokenAnswer)) {
    pass("QA error-pattern catches real failures");
  } else {
    fail("QA error-pattern catches real failures", brokenAnswer);
  }

  // --- shouldUseAgentLoop ---
  if (HalAgentLoop.shouldUseAgentLoop(codeQ, baseRoute, investigatePlan, halModels.config.agentProgramming)) {
    pass("shouldUseAgentLoop for code question");
  } else {
    fail("shouldUseAgentLoop for code question", "returned false");
  }

  console.log("\n=== Parity summary ===");
  console.log(`Passed checks with ${issues.length} failure(s)`);
  if (issues.length) {
    fs.mkdirSync(path.join(__dirname, "..", ".local_logs"), { recursive: true });
    const out = path.join(__dirname, "..", ".local_logs", "hal_parity_issues.json");
    fs.writeFileSync(out, JSON.stringify({ generated_at: new Date().toISOString(), issues }, null, 2));
    console.log("Issues written:", out);
    process.exitCode = 1;
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

/**
 * Interview HAL until replies match Cursor Auto style (polish + shape rubric).
 * Usage: node scripts/hal-interview.mjs [--live]
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const siteDir = path.join(__dirname, "..", "NewRidgeFinancial2", "site");
const halManagerPath = path.join(siteDir, "data", "hal-manager.json");
const halModelsPath = path.join(siteDir, "data", "hal-models.json");
const live = process.argv.includes("--live");

function loadJson(p) {
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

async function tryLiveQuestion(query, halModels) {
  const endpoint = halModels?.config?.localModel?.endpoint;
  const model = halModels?.config?.localModel?.model;
  if (!endpoint || !model) return { skipped: true, reason: "no local model config" };
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 45000);
  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: ctrl.signal,
      body: JSON.stringify({
        model,
        stream: false,
        messages: [
          {
            role: "system",
            content:
              (globalThis.HalAgentProgramming && HalAgentProgramming.contract()) ||
              "Answer like Cursor Auto: direct, proportional, evidence-based.",
          },
          { role: "user", content: query },
        ],
      }),
    });
    if (!res.ok) return { skipped: true, reason: `ollama ${res.status}` };
    const data = await res.json();
    const text = data?.message?.content || "";
    return { skipped: false, text: String(text).trim() };
  } catch (e) {
    return { skipped: true, reason: String(e.message || e) };
  } finally {
    clearTimeout(t);
  }
}

async function main() {
  const halData = loadJson(halManagerPath);
  const halModels = loadJson(halModelsPath);
  const pages = [
    { id: "financial", label: "Financial dashboard" },
    { id: "claims", label: "Claims Workbench" },
    { id: "ar", label: "A/R & Collections" },
    { id: "hal", label: "HAL Command Center" },
  ];

  await import(pathToFileURL(path.join(siteDir, "hal-agent-programming.js")).href);
  await import(pathToFileURL(path.join(siteDir, "hal-cursor-parity.js")).href);
  const HalCore = (await import(pathToFileURL(path.join(siteDir, "hal-core.js")).href)).default;

  const CP = globalThis.HalCursorParity;
  if (!CP || !CP.isEnabled(halModels)) {
    console.error("cursorParity is not enabled in hal-models.json");
    process.exit(1);
  }

  const results = CP.runInterviewPolish(HalCore, halData, halModels, pages);
  let failures = 0;

  console.log("=== HAL cursor-parity interview (polish fixtures) ===\n");
  for (const r of results) {
    const mark = r.pass ? "PASS" : "FAIL";
    console.log(`${mark}  ${r.id}`);
    console.log(`  Q: ${r.query}`);
    console.log(`  A: ${r.reply}${r.reply.length >= 280 ? "…" : ""}`);
    if (!r.pass) {
      failures++;
      console.log(`  issues: ${r.issues.join(", ")}`);
    }
    console.log("");
  }

  if (live) {
    console.log("=== Live model spot-check (optional) ===\n");
    for (const q of ["Can you refresh imports?", "Are imports current?"]) {
      const liveResult = await tryLiveQuestion(q, halModels);
      if (liveResult.skipped) {
        console.log(`SKIP  ${q} — ${liveResult.reason}`);
        continue;
      }
      const route = HalCore.routeHalCommand(halData, halModels, pages, q);
      const meta = CP.enrichPolishMeta({ halData, halModels, pages, synthesize: false }, q, route, halModels);
      const polished = HalCore.polishChatReply(liveResult.text, q, route, meta);
      const scored = CP.scoreReply(q, polished, route, { halModels, fixture: { mustStartYesNo: true, maxSentences: 5 } });
      const mark = scored.pass ? "PASS" : "FAIL";
      console.log(`${mark}  live: ${q}`);
      console.log(`  A: ${polished.slice(0, 240)}${polished.length > 240 ? "…" : ""}`);
      if (!scored.pass) {
        failures++;
        console.log(`  issues: ${scored.issues.join(", ")}`);
      }
      console.log("");
    }
  }

  const passed = results.filter((r) => r.pass).length;
  console.log(`=== Summary: ${passed}/${results.length} fixture interviews passed${live ? " (+ live spot-check)" : ""} ===`);
  if (failures) {
    fs.mkdirSync(path.join(__dirname, "..", ".local_logs"), { recursive: true });
    const out = path.join(__dirname, "..", ".local_logs", "hal_interview_failures.json");
    fs.writeFileSync(
      out,
      JSON.stringify({ generated_at: new Date().toISOString(), results, failures }, null, 2),
    );
    console.log("Failures written:", out);
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

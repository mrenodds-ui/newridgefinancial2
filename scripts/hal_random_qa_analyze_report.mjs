/**
 * Post-process hal_random_qa_latest.json: Cursor parity scoring in browser + markdown report.
 * Does not modify HAL site source.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");
const require = createRequire(import.meta.url);
const { chromium } = require(path.join(REPO_ROOT, "frontend", "node_modules", "playwright"));
const BASE_URL = process.env.NR2_BASE_URL || "http://127.0.0.1:8765";
const JSON_PATH = process.env.HAL_QA_JSON || path.join(REPO_ROOT, ".local_logs", "hal_random_qa_latest.json");
const OUT_MD = path.join(REPO_ROOT, ".local_logs", "hal_random_qa_report.md");

function snippet(s, n = 220) {
  const t = String(s || "").replace(/\s+/g, " ").trim();
  return t.length <= n ? t : t.slice(0, n) + "…";
}

function extraFlags(turn) {
  const flags = [];
  const a = String(turn.a || "");
  const q = String(turn.q || "");
  if (!a.trim()) flags.push("empty_answer");
  if (/question timeout after/i.test(a) || turn.issue === "timeout") flags.push("timeout");
  if (turn.issue === "instruction_leak" || /local tool check|synthesize tool results|do not paste tool headers/i.test(a)) {
    flags.push("instruction_leak");
  }
  if (/hit an error|could not finish|could not complete that request|check that ollama is running/i.test(a)) {
    flags.push("runtime_error_text");
  }
  if (turn.lane === "error" || turn.error) flags.push("harness_error_flag");
  if (/HAL PROGRAM SNAPSHOT/i.test(a)) flags.push("program_snapshot_dump");
  if (/\b(I am HAL|ship computer|operational intelligence)\b/i.test(a)) flags.push("identity_monologue");
  if (/\b(happy to help|let me know if|feel free to ask|great question)\b/i.test(a)) flags.push("chatbot_filler");
  if (turn.lane === "error" && /timeout/i.test(a)) flags.push("timeout");
  return flags;
}

async function scoreTurnsInBrowser(turns) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto(`${BASE_URL}/#hal?v=${Date.now()}`, { waitUntil: "domcontentloaded", timeout: 120000 });
  await page.waitForFunction(
    () => typeof HalCursorParity !== "undefined" && HalCursorParity.scoreReply && typeof halModels !== "undefined",
    { timeout: 180000 },
  );

  const batchSize = 25;
  const scored = [];
  for (let i = 0; i < turns.length; i += batchSize) {
    const batch = turns.slice(i, i + batchSize);
    const part = await page.evaluate(
      ({ items }) => {
        const out = [];
        for (const t of items) {
          const route = { intent: t.intent || "", lane: t.lane || "" };
          const opts = { halModels };
          if (/^capability:/.test(route.intent || "")) opts.skipMinSentences = true;
          const r = HalCursorParity.scoreReply(t.q, t.a, route, opts);
          out.push({ pass: r.pass, score: r.score, issues: r.issues || [] });
        }
        return out;
      },
      { items: batch.map((t) => ({ q: t.q, a: t.a, intent: t.intent, lane: t.lane })) },
    );
    scored.push(...part);
  }
  await browser.close();
  return scored;
}

function buildMarkdown(report, enrichedTurns, issueCounts) {
  const s = report.summary || {};
  const parity = report.cursor_parity || {};
  const lines = [];
  lines.push("# HAL random QA report (100 questions)");
  lines.push("");
  lines.push(`Generated: ${report.generated_at || new Date().toISOString()}`);
  lines.push(`Base URL: ${report.base_url || BASE_URL}`);
  lines.push("");
  lines.push("## Totals");
  lines.push("");
  lines.push(`| Metric | Count |`);
  lines.push(`|--------|------:|`);
  lines.push(`| Completed | ${s.completed ?? enrichedTurns.length} |`);
  lines.push(`| Harness flagged errors | ${s.flagged_errors ?? 0} |`);
  lines.push(`| Empty answers | ${s.empty_answers ?? 0} |`);
  lines.push(`| Timeouts (detected) | ${parity.timeouts ?? 0} |`);
  lines.push(`| Instruction leaks | ${parity.instruction_leaks ?? 0} |`);
  lines.push(`| Runtime elapsed (sec) | ${s.elapsed_sec ?? "n/a"} |`);
  lines.push("");
  lines.push("## Cursor parity");
  lines.push("");
  lines.push(`| Metric | Value |`);
  lines.push(`|--------|------:|`);
  lines.push(`| Pass | ${parity.pass_count ?? 0} |`);
  lines.push(`| Fail | ${parity.fail_count ?? 0} |`);
  lines.push(`| Average score | ${parity.avg_score ?? 0} |`);
  lines.push("");
  lines.push("## Top issue types");
  lines.push("");
  const sorted = Object.entries(issueCounts).sort((a, b) => b[1] - a[1]);
  if (!sorted.length) lines.push("_None_");
  else for (const [k, v] of sorted.slice(0, 25)) lines.push(`- **${k}**: ${v}`);
  lines.push("");

  const bad = enrichedTurns.filter(
    (t) =>
      t.error ||
      t.lane === "error" ||
      !t.parity_pass ||
      (t.all_issues && t.all_issues.length),
  );
  const problem = bad.filter(
    (t) =>
      t.error ||
      t.lane === "error" ||
      !t.parity_pass ||
      t.all_issues.some((i) =>
        ["empty_answer", "timeout", "instruction_leak", "runtime_error_text", "runtime_error", "empty_response"].includes(
          i,
        ),
      ),
  );

  lines.push("## All error / timeout / failed-parity entries");
  lines.push("");
  if (!problem.length) lines.push("_No problematic entries detected._");
  else {
    for (const t of problem) {
      lines.push(`### #${t.n}`);
      lines.push(`**Q:** ${t.q}`);
      lines.push("");
      lines.push(`**A:** ${snippet(t.a, 400)}`);
      lines.push("");
      lines.push(`**Issues:** ${(t.all_issues || []).join(", ") || "none"}`);
      lines.push(`**Parity:** pass=${t.parity_pass} score=${t.parity_score}`);
      lines.push("");
    }
  }

  const good = enrichedTurns
    .filter((t) => t.parity_pass && (t.parity_score ?? 0) >= 88 && !t.error)
    .sort((a, b) => (b.parity_score ?? 0) - (a.parity_score ?? 0))
    .slice(0, 5);
  lines.push("## Sample good replies (high parity score)");
  lines.push("");
  for (const t of good) {
    lines.push(`- **#${t.n}** (score ${t.parity_score}): _${snippet(t.q, 80)}_ → ${snippet(t.a, 160)}`);
  }
  lines.push("");
  lines.push("## Artifacts");
  lines.push("");
  lines.push(`- Full JSON: \`${JSON_PATH.replace(/\\/g, "/")}\``);
  lines.push("");
  return lines.join("\n");
}

async function main() {
  const raw = JSON.parse(fs.readFileSync(JSON_PATH, "utf8"));
  const turns = raw.turns || [];
  console.log(`Scoring ${turns.length} turns via HalCursorParity in browser...`);
  const parityResults = await scoreTurnsInBrowser(turns);

  const issueCounts = {};
  const bump = (k) => {
    issueCounts[k] = (issueCounts[k] || 0) + 1;
  };

  let passCount = 0;
  let failCount = 0;
  let scoreSum = 0;
  let timeouts = 0;
  let instructionLeaks = 0;

  const enrichedTurns = turns.map((t, idx) => {
    const pr = parityResults[idx] || { pass: false, score: 0, issues: [] };
    const extras = extraFlags(t);
    const allIssues = [...new Set([...(pr.issues || []), ...extras])];
    for (const i of allIssues) bump(i);
    if (pr.pass) passCount++;
    else failCount++;
    scoreSum += pr.score ?? 0;
    if (extras.includes("timeout")) timeouts++;
    if (extras.includes("instruction_leak") || allIssues.includes("instruction_leak")) instructionLeaks++;

    return {
      ...t,
      parity_pass: pr.pass && allIssues.length === 0 ? true : pr.pass && extras.length === 0,
      parity_score: pr.score,
      parity_issues: pr.issues,
      extra_flags: extras,
      all_issues: allIssues,
    };
  });

  const avgScore = turns.length ? Math.round((scoreSum / turns.length) * 10) / 10 : 0;
  raw.cursor_parity = {
    pass_count: enrichedTurns.filter((t) => t.parity_pass).length,
    fail_count: enrichedTurns.filter((t) => !t.parity_pass).length,
    avg_score: avgScore,
    timeouts,
    instruction_leaks: instructionLeaks,
    scored_at: new Date().toISOString(),
  };
  raw.turns = enrichedTurns;
  fs.writeFileSync(JSON_PATH, JSON.stringify(raw, null, 2), "utf8");

  const md = buildMarkdown(raw, enrichedTurns, issueCounts);
  fs.writeFileSync(OUT_MD, md, "utf8");
  console.log(`Wrote ${OUT_MD}`);
  console.log(JSON.stringify(raw.cursor_parity, null, 2));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

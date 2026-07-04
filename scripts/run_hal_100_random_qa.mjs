/**
 * Run 100 random HAL questions through the NR2 UI (handleHalSubmit inject).
 * Requires NR2 desktop on http://127.0.0.1:8765/
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
const QUESTION_COUNT = Math.max(1, Math.min(500, Number(process.env.HAL_QA_COUNT) || 100));
const SKIP_SPEECH = process.env.HAL_QA_SKIP_SPEECH !== "0";
const USE_REASONING = process.env.HAL_QA_REASONING !== "0";
const OUTPUT_DIR = path.join(REPO_ROOT, ".local_logs");
const INJECT_PATH = path.join(REPO_ROOT, "scripts", "hal_random_qa_inject.js");

function waitForServer(url, timeoutMs = 120000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const tick = async () => {
      try {
        const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
        if (res.ok) {
          resolve();
          return;
        }
      } catch (_) {}
      if (Date.now() - started > timeoutMs) {
        reject(new Error(`Server not ready at ${url} after ${timeoutMs}ms`));
        return;
      }
      setTimeout(tick, 1500);
    };
    tick();
  });
}

async function run() {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const injectSource = fs.readFileSync(INJECT_PATH, "utf8");

  console.log(`Waiting for ${BASE_URL} ...`);
  await waitForServer(BASE_URL);

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.setDefaultTimeout(120000);
  const consoleErrors = [];
  const pageErrors = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => {
    pageErrors.push(err.message || String(err));
  });

  console.log("Opening HAL Command Center ...");
  await page.goto(`${BASE_URL}/#hal`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForFunction(
    () =>
      typeof handleHalSubmit === "function" &&
      typeof HalCore !== "undefined" &&
      HalCore.laneRuntime(halModels, "chat8b"),
    { timeout: 120000 },
  );
  await page.evaluate(async () => {
    if (typeof ensureOllamaModelCache === "function") await ensureOllamaModelCache(0);
  });

  console.log(
    `Starting ${QUESTION_COUNT} random questions (skipSpeech=${SKIP_SPEECH}, reasoning=${USE_REASONING}) ...`,
  );

  const startMsg = await page.evaluate(
    ({ count, skipSpeech, useReasoning, source }) => {
      window._halRandomQaCount = count;
      window._halRandomQaSkipSpeech = skipSpeech;
      window._halRandomQaUseReasoning = useReasoning;
      // eslint-disable-next-line no-eval
      return eval(source);
    },
    {
      count: QUESTION_COUNT,
      skipSpeech: SKIP_SPEECH,
      useReasoning: USE_REASONING,
      source: injectSource,
    },
  );
  console.log(startMsg);

  const pollIntervalMs = 5000;
  let lastCompleted = -1;
  while (true) {
    const status = await page.evaluate(() => {
      const run = window._halRandomQaRun || {};
      return {
        running: !!run.running,
        total: run.total || 0,
        completed: run.completed || 0,
        errors: run.errors || 0,
        empty: run.empty || 0,
        current: run.current || "",
        elapsedSec: run.elapsedSec || null,
      };
    });

    if (status.completed !== lastCompleted) {
      lastCompleted = status.completed;
      console.log(
        `[${status.completed}/${status.total}] errors=${status.errors} empty=${status.empty} elapsed=${status.elapsedSec ?? "…"}s`,
      );
      if (status.current) {
        console.log(`  Q: ${String(status.current).slice(0, 100)}`);
      }
    }

    if (!status.running && status.total > 0 && status.completed >= status.total) break;
    await page.waitForTimeout(pollIntervalMs);
  }

  const result = await page.evaluate(() => ({
    run: window._halRandomQaRun || null,
    log: window._halRandomQaLog || [],
  }));

  await browser.close();

  const errorEntries = result.log.filter((e) => e.error);
  const errorPatterns = result.log.filter((e) =>
    /hit an error|could not finish|did not return a response/i.test(String(e.a || "")),
  );

  const report = {
    generated_at: new Date().toISOString(),
    base_url: BASE_URL,
    question_count: QUESTION_COUNT,
    skip_speech: SKIP_SPEECH,
    use_reasoning: USE_REASONING,
    summary: {
      total: result.run?.total ?? result.log.length,
      completed: result.run?.completed ?? result.log.length,
      flagged_errors: result.run?.errors ?? errorEntries.length,
      empty_answers: result.run?.empty ?? 0,
      error_entries: errorEntries.length,
      error_pattern_matches: errorPatterns.length,
      console_error_count: consoleErrors.length,
      page_error_count: pageErrors.length,
      elapsed_sec: result.run?.elapsedSec ?? null,
    },
    console_errors: consoleErrors.slice(0, 200),
    page_errors: pageErrors.slice(0, 50),
    error_entries: errorEntries,
    error_pattern_matches: errorPatterns,
    turns: result.log,
  };

  const stamp = new Date().toISOString().replaceAll(":", "-");
  const outPath = path.join(OUTPUT_DIR, `hal_random_qa_${stamp}.json`);
  const latestPath = path.join(OUTPUT_DIR, "hal_random_qa_latest.json");
  fs.writeFileSync(outPath, JSON.stringify(report, null, 2), "utf8");
  fs.writeFileSync(latestPath, JSON.stringify(report, null, 2), "utf8");

  console.log("\n=== HAL 100-question QA summary ===");
  console.log(JSON.stringify(report.summary, null, 2));
  console.log(`Report: ${outPath}`);

  if (
    report.summary.flagged_errors > 0 ||
    report.summary.page_error_count > 0 ||
    report.summary.console_error_count > 0
  ) {
    process.exitCode = 1;
  }

  return report;
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});

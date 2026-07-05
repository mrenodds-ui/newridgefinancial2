/**
 * Live HAL cursor-parity interview via NR2 desktop UI (handleHalSubmit).
 * Usage: node scripts/hal-interview-live.mjs [--restart]
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { spawn } from "node:child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");
const require = createRequire(import.meta.url);
const { chromium } = require(path.join(REPO_ROOT, "frontend", "node_modules", "playwright"));
const BASE_URL = process.env.NR2_BASE_URL || "http://127.0.0.1:8765";
const OUTPUT_DIR = path.join(REPO_ROOT, ".local_logs");
const INJECT_PATH = path.join(REPO_ROOT, "scripts", "hal_interview_inject.js");
const doRestart = process.argv.includes("--restart");

function waitForServer(url, timeoutMs = 180000) {
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

async function restartProgram() {
  console.log("Restarting Start Program …");
  return new Promise((resolve, reject) => {
    const ps = spawn(
      "powershell",
      [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        path.join(REPO_ROOT, "scripts", "start_program.ps1"),
        "-Restart",
        "-SkipValidation",
      ],
      { cwd: REPO_ROOT, stdio: "inherit", detached: true },
    );
    ps.on("error", reject);
    ps.unref();
    setTimeout(resolve, 8000);
  });
}

async function main() {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const injectSource = fs.readFileSync(INJECT_PATH, "utf8");

  if (doRestart) {
    await restartProgram();
  }

  console.log(`Waiting for ${BASE_URL} …`);
  await waitForServer(BASE_URL);

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.setDefaultTimeout(180000);

  console.log("Opening HAL Command Center …");
  await page.goto(`${BASE_URL}/#hal?v=${Date.now()}`, { waitUntil: "domcontentloaded", timeout: 90000 });
  await page.waitForFunction(
    () =>
      typeof handleHalSubmit === "function" &&
      typeof HalCore !== "undefined" &&
      typeof HalCursorParity !== "undefined" &&
      HalCursorParity.isEnabled(halModels),
    { timeout: 180000 },
  );

  const startMsg = await page.evaluate(
    ({ source }) => {
      window._halInterviewSkipSpeech = true;
      window._halInterviewTimeoutMs = 240000;
      window._halInterviewMode = true;
      window._halForceReasoning = false;
      // eslint-disable-next-line no-eval
      return eval(source);
    },
    { source: injectSource },
  );
  console.log(startMsg);

  while (true) {
    let status;
    try {
      status = await page.evaluate(() => {
        const run = window._halInterviewRun || {};
        return {
          running: !!run.running,
          total: run.total || 0,
          completed: run.completed || 0,
          passed: run.passed || 0,
          failed: run.failed || 0,
          current: run.current || "",
        };
      });
    } catch (err) {
      console.warn("Interview poll error — reloading HAL:", err.message);
      await page.goto(`${BASE_URL}/#hal?v=${Date.now()}`, { waitUntil: "domcontentloaded", timeout: 90000 });
      await page.waitForFunction(() => typeof handleHalSubmit === "function", { timeout: 120000 });
      continue;
    }
    if (!status.running && status.total > 0 && status.completed >= status.total) break;
    console.log(
      `[${status.completed}/${status.total}] pass=${status.passed} fail=${status.failed}` +
        (status.current ? `  Q: ${String(status.current).slice(0, 72)}` : ""),
    );
    await page.waitForTimeout(4000);
  }

  const result = await page.evaluate(() => ({
    run: window._halInterviewRun || null,
    log: window._halInterviewLog || [],
  }));
  await browser.close();

  const failures = result.log.filter((e) => !e.pass);
  const report = {
    generated_at: new Date().toISOString(),
    base_url: BASE_URL,
    summary: {
      total: result.run?.total ?? result.log.length,
      passed: result.run?.passed ?? result.log.filter((e) => e.pass).length,
      failed: failures.length,
      elapsedSec: result.run?.elapsedSec ?? null,
    },
    failures: failures.map((f) => ({
      id: f.id,
      q: f.q,
      issues: f.issues,
      a: String(f.a || "").slice(0, 400),
      error: f.error,
    })),
    log: result.log,
  };

  const outPath = path.join(OUTPUT_DIR, "hal_cursor_interview_live.json");
  fs.writeFileSync(outPath, JSON.stringify(report, null, 2));

  console.log("\n=== Live cursor interview ===");
  for (const entry of result.log) {
    const mark = entry.pass ? "PASS" : "FAIL";
    console.log(`${mark}  ${entry.id}`);
    console.log(`  Q: ${entry.q}`);
    console.log(`  A: ${String(entry.a || entry.error || "").slice(0, 220)}${String(entry.a || "").length > 220 ? "…" : ""}`);
    if (!entry.pass) console.log(`  issues: ${(entry.issues || []).join(", ")}`);
    console.log("");
  }

  console.log(
    `=== Summary: ${report.summary.passed}/${report.summary.total} passed (${report.summary.elapsedSec ?? "?"}s) ===`,
  );
  console.log("Report:", outPath);

  if (failures.length) process.exit(1);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

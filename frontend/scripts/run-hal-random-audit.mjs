import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";
import { installHalApiAuth } from "./halAuditAuth.mjs";

const QUESTION_POOL = [
  "What pages and major workflows exist in this program right now?",
  "Summarize the current dashboard architecture in plain language.",
  "Which route should I open for the main financial dashboard and why?",
  "What does the SoftDent page focus on, based only on this system's available data?",
  "What does the QuickBooks page focus on, based only on this system's available data?",
  "Explain how HAL is supposed to stay read-only unless a reviewed action is approved.",
  "What does the A/R collections view appear to measure?",
  "What does the trends page appear to compare over time?",
  "What is the purpose of the accounting policy page?",
  "What is the purpose of the posting queue review page?",
  "If I asked for a KPI that is not in the verified data, how should you respond?",
  "Give me the latest production and collections picture if the current page summary has it.",
  "What does the system say about missing SoftDent coverage or unavailable reports?",
  "How would you describe the source review concept to an office manager?",
  "What should I verify first if the dashboard numbers look stale?",
  "How should I interpret a collection rate drop from the latest monthly KPI row?",
  "What follow-up would you recommend if patient A/R is rising faster than insurance A/R?",
  "What operational risk do you see if outstanding claims exports are missing?",
  "How would you explain trailing-12 totals versus a single current month?",
  "If the trends page shows production up but net income down, what might that imply?",
  "What would you want to confirm before making decisions from the QuickBooks expense trend?",
  "Summarize the difference between production, collections, and net income.",
  "If payroll is the largest expense category, what management questions should I ask next?",
  "What does a verified QuickBooks revenue source tell me versus a missing one?",
  "If A/R aging shifts into older buckets, what action plan would you suggest?",
  "How would you explain current balance, 30-day, 60-day, and 90-day buckets to a front desk lead?",
  "What does this program appear to use from SoftDent versus QuickBooks?",
  "How would you brief me on the data boundaries of this app in two sentences?",
  "What is the safest way to ask you for accounting guidance without overreaching past the data?",
  "If a provider looks weak, what evidence should I confirm before coaching them?",
  "What SoftDent data would be most important for same-day production follow-up?",
  "What QuickBooks data would be most important for overhead control?",
  "How would you investigate a collections gap using only the approved local data?",
  "What is the likely purpose of the HAL landing page versus the Ask HAL page?",
  "What should I ask next if I want to understand profitability instead of production?",
  "If I say 'post a QuickBooks adjustment now', what should you do?",
  "If I say 'change the monitor brightness to 30 percent', what should you do?",
  "If I ask for patient-specific advice without enough verified facts, how should you respond?",
  "What program-level facts can you state confidently without inventing anything?",
  "How would you compare the dashboard page and the trends page for a doctor owner?",
  "What do you think this system is trying to prevent with review-required actions?",
  "What unanswered question would you ask me before recommending a collections fix?",
  "How should I use this app to prepare for a morning huddle?",
  "How should I use this app to prepare for a month-end review?",
  "What would make you warn me that the available data is incomplete?",
  "What is the most important caution when discussing QuickBooks net income here?",
  "What is the most important caution when discussing SoftDent production here?",
  "If I need a concise practice-health summary, what categories would you include?",
  "Give me a short summary of the top financial questions this program seems built to answer.",
  "Based on everything above, what are the top three follow-up questions I should ask next?",
];

const BASE_URL = process.env.HAL_AUDIT_BASE_URL || "http://127.0.0.1:5173";
const ROOT = path.resolve(import.meta.dirname, "..");
const OUTPUT_DIR = path.resolve(ROOT, "..", "DataAnalysisExpert", "outputs", "hal_random_audit");
const PROGRESS_LOG = path.join(OUTPUT_DIR, "hal_random_audit_progress.log");

function shuffledQuestions() {
  const questions = [...QUESTION_POOL];
  for (let index = questions.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [questions[index], questions[swapIndex]] = [questions[swapIndex], questions[index]];
  }
  return questions.slice(0, 50);
}

function appendProgress(message) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  fs.appendFileSync(PROGRESS_LOG, `[${new Date().toISOString()}] ${message}\n`, "utf8");
}

function attachBrowserEventCapture(page, browserEvents, currentTurnRef) {
  page.on("console", (message) => {
    if (message.type() !== "error") {
      return;
    }
    browserEvents.push({
      type: "console",
      message: message.text(),
      turn: currentTurnRef.current || null,
      timestamp: new Date().toISOString(),
    });
  });

  page.on("pageerror", (error) => {
    browserEvents.push({
      type: "pageerror",
      message: error.message,
      turn: currentTurnRef.current || null,
      timestamp: new Date().toISOString(),
    });
  });

  page.on("requestfailed", (request) => {
    browserEvents.push({
      type: "requestfailed",
      message: request.failure()?.errorText || "request failed",
      url: request.url(),
      turn: currentTurnRef.current || null,
      timestamp: new Date().toISOString(),
    });
  });
}

async function waitForHalResult(page, previousAnswer) {
  const answerCard = page.locator(".hal-answer-card").filter({ has: page.getByRole("heading", { name: "HAL's Answer" }) }).first();
  const answerLead = answerCard.locator(".hal-answer-card__section--lead").first();
  const errorCard = page.locator(".hal-answer-card").filter({ has: page.getByRole("heading", { name: "Request failed" }) }).first();
  const deadline = Date.now() + 180000;

  while (Date.now() < deadline) {
    const errorVisible = await errorCard.isVisible().catch(() => false);
    if (errorVisible) {
      const errorText = ((await errorCard.innerText().catch(() => "")) || "HAL request failed without visible details.").trim();
      return { status: "error", answer: "", error: errorText };
    }

    const answerVisible = await answerCard.isVisible().catch(() => false);
    if (answerVisible) {
      const answerText = ((await answerLead.textContent().catch(() => "")) || "").trim();
      if (answerText && answerText !== previousAnswer) {
        return { status: "ok", answer: answerText };
      }
    }

    await page.waitForTimeout(500);
  }

  return {
    status: "error",
    answer: "",
    error: "Timed out waiting for HAL to produce a new answer.",
  };
}

async function askHal(page, question) {
  const started = Date.now();
  const textarea = page.getByLabel("Your Question");
  const answerCard = page.locator(".hal-answer-card").filter({ has: page.getByRole("heading", { name: "HAL's Answer" }) }).first();
  const answerLead = answerCard.locator(".hal-answer-card__section--lead").first();
  const previousAnswer = (await answerCard.isVisible().catch(() => false))
    ? (((await answerLead.textContent().catch(() => "")) || "").trim())
    : "";

  await textarea.fill(question);
  await page.getByRole("button", { name: "Ask HAL", exact: true }).click();

  const result = await waitForHalResult(page, previousAnswer);

  return {
    question,
    status: result.status,
    elapsed_seconds: (Date.now() - started) / 1000,
    answer: result.answer,
    answer_length: result.answer.length,
    error: result.error || null,
  };
}

async function run() {
  const questions = shuffledQuestions();
  const browserEvents = [];
  const currentTurnRef = { current: 0 };
  const report = {
    generated_at: new Date().toISOString(),
    base_url: BASE_URL,
    question_count: questions.length,
    failed_turns: 0,
    browser_event_count: 0,
    startup_error: null,
    turns: [],
    browser_events: browserEvents,
  };

  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  fs.writeFileSync(PROGRESS_LOG, "", "utf8");
  appendProgress(`starting audit against ${BASE_URL}`);

  appendProgress("launching chromium");
  const browser = await chromium.launch({ headless: true });
  appendProgress("chromium launched");
  const context = await browser.newContext();
  const page = await context.newPage();
  appendProgress("browser context and page ready");

  attachBrowserEventCapture(page, browserEvents, currentTurnRef);

  await installHalApiAuth(page);
  appendProgress("api auth route installed");

  try {
    appendProgress("navigating to HAL page");
    await page.goto(`${BASE_URL}/app/hal`, { waitUntil: "domcontentloaded", timeout: 60000 });
    appendProgress("HAL page DOM loaded");
    await page.getByRole("heading", { name: "Ask Hal 9000" }).waitFor({ state: "visible", timeout: 60000 });
    appendProgress("HAL heading visible");

    for (const [index, question] of questions.entries()) {
      currentTurnRef.current = index + 1;
      appendProgress(`turn ${index + 1} start`);
      const turn = await askHal(page, question);
      report.turns.push({ turn: index + 1, ...turn });
      appendProgress(`turn ${index + 1} ${turn.status}`);
    }
  } catch (error) {
    report.startup_error = error instanceof Error ? error.message : String(error);
    appendProgress(`startup error: ${report.startup_error}`);
  } finally {
    report.failed_turns = report.turns.filter((turn) => turn.status === "error").length;
    report.browser_event_count = browserEvents.length;

    const stamp = new Date().toISOString().replaceAll(":", "-");
    const timestampedPath = path.join(OUTPUT_DIR, `hal_random_audit_${stamp}.json`);
    const latestPath = path.join(OUTPUT_DIR, "hal_random_audit_latest.json");
    fs.writeFileSync(timestampedPath, JSON.stringify(report, null, 2), "utf8");
    fs.writeFileSync(latestPath, JSON.stringify(report, null, 2), "utf8");

    console.log(JSON.stringify({
      output: timestampedPath,
      startup_error: report.startup_error,
      failed_turns: report.failed_turns,
      browser_event_count: report.browser_event_count,
    }));
    appendProgress(`report written: ${timestampedPath}`);

    await browser.close();
    appendProgress("browser closed");
  }
}

run().catch((error) => {
  const fallbackReport = {
    generated_at: new Date().toISOString(),
    base_url: BASE_URL,
    question_count: 50,
    failed_turns: 0,
    browser_event_count: 0,
    startup_error: error instanceof Error ? error.message : String(error),
    turns: [],
    browser_events: [],
  };

  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const latestPath = path.join(OUTPUT_DIR, "hal_random_audit_latest.json");
  fs.writeFileSync(PROGRESS_LOG, `[${new Date().toISOString()}] fatal error: ${fallbackReport.startup_error}\n`, "utf8");
  fs.writeFileSync(latestPath, JSON.stringify(fallbackReport, null, 2), "utf8");
  console.log(JSON.stringify({ output: latestPath, startup_error: fallbackReport.startup_error }));
});
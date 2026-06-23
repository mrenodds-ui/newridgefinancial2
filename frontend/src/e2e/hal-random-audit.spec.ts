import fs from "node:fs";
import path from "node:path";
import { type Page, expect, test } from "@playwright/test";
import { halEvalCredentialsConfigured, installHalApiAuth } from "./halAuth";

const QUESTIONS = [
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
  "If I asked for a fake KPI that is not in the verified data, how should you respond?",
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

type BrowserEvent = {
  type: "console" | "pageerror" | "requestfailed";
  message: string;
  url?: string;
  turn?: number;
  timestamp: string;
};

type TurnRecord = {
  turn: number;
  question: string;
  status: "ok" | "error";
  elapsed_seconds: number;
  answer: string;
  answer_length: number;
  error?: string;
};

test.skip(!halEvalCredentialsConfigured, "Set HAL_EVAL_USERNAME and HAL_EVAL_PASSWORD to run HAL audit specs.");

function attachBrowserEventCapture(page: Page, browserEvents: BrowserEvent[], currentTurnRef: { current: number }) {
  page.on("console", (message) => {
    if (message.type() !== "error") {
      return;
    }
    browserEvents.push({
      type: "console",
      message: message.text(),
      turn: currentTurnRef.current || undefined,
      timestamp: new Date().toISOString(),
    });
  });
  page.on("pageerror", (error) => {
    browserEvents.push({
      type: "pageerror",
      message: error.message,
      turn: currentTurnRef.current || undefined,
      timestamp: new Date().toISOString(),
    });
  });
  page.on("requestfailed", (request) => {
    const failure = request.failure();
    browserEvents.push({
      type: "requestfailed",
      message: failure?.errorText || "request failed",
      url: request.url(),
      turn: currentTurnRef.current || undefined,
      timestamp: new Date().toISOString(),
    });
  });
}

async function askHal(page: Page, question: string): Promise<TurnRecord> {
  const started = Date.now();
  const textarea = page.getByLabel("Your Question");
  const answerCard = page.locator(".hal-answer-card").filter({ has: page.getByRole("heading", { name: "HAL's Answer" }) }).first();
  const answerLead = answerCard.locator(".hal-answer-card__section--lead").first();
  const previousAnswer = (await answerCard.isVisible().catch(() => false)) ? (((await answerLead.textContent()) ?? "").trim()) : "";

  await textarea.fill(question);
  await page.getByRole("button", { name: "Ask HAL", exact: true }).click();

  try {
    await expect(answerCard).toBeVisible({ timeout: 180000 });
    await expect(answerLead).not.toHaveText(/^\s*$/, { timeout: 180000 });
    if (previousAnswer) {
      await expect(answerLead).not.toHaveText(previousAnswer, { timeout: 180000 });
    }

    const answer = (await answerLead.innerText()).trim();

    return {
      turn: 0,
      question,
      status: "ok",
      elapsed_seconds: (Date.now() - started) / 1000,
      answer,
      answer_length: answer.length,
    };
  } catch (error) {
    return {
      turn: 0,
      question,
      status: "error",
      elapsed_seconds: (Date.now() - started) / 1000,
      answer: "",
      answer_length: 0,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

test("runs a 50-question HAL UI audit and saves transcript plus error report", async ({ page }, testInfo) => {
  test.setTimeout(90 * 60 * 1000);

  const browserEvents: BrowserEvent[] = [];
  const currentTurnRef = { current: 0 };

  attachBrowserEventCapture(page, browserEvents, currentTurnRef);
  await installHalApiAuth(page);
  await page.goto("/app/hal");
  await expect(page.getByRole("heading", { name: "Ask Hal 9000" })).toBeVisible();

  const turns: TurnRecord[] = [];
  for (const [index, question] of QUESTIONS.entries()) {
    currentTurnRef.current = index + 1;
    const turn = await askHal(page, question);
    turn.turn = index + 1;
    turns.push(turn);
  }

  const outputDir = path.resolve(process.cwd(), "..", "DataAnalysisExpert", "outputs", "hal_random_audit");
  fs.mkdirSync(outputDir, { recursive: true });

  const report = {
    generated_at: new Date().toISOString(),
    base_url: testInfo.project.use.baseURL,
    question_count: QUESTIONS.length,
    failed_turns: turns.filter((turn) => turn.status === "error").length,
    browser_event_count: browserEvents.length,
    turns,
    browser_events: browserEvents,
  };

  const stamp = new Date().toISOString().replaceAll(":", "-");
  fs.writeFileSync(path.join(outputDir, `hal_random_audit_${stamp}.json`), JSON.stringify(report, null, 2), "utf8");
  fs.writeFileSync(path.join(outputDir, "hal_random_audit_latest.json"), JSON.stringify(report, null, 2), "utf8");

  expect(QUESTIONS).toHaveLength(50);
});
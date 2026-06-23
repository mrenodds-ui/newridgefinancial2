import fs from "node:fs";
import path from "node:path";
import { type Page, expect, test } from "@playwright/test";
import { halEvalCredentialsConfigured, installHalApiAuth } from "./halAuth";

const CONVERSATION = [
  "Give me the current HAL operating picture and local runtime posture in plain language.",
  "Based on that, what should I do first before lunch about the collections gap?",
  "Which provider is the weakest right now and why?",
  "Patient John Doe MRN 778899 needs help on the denied crown buildup claim.",
  "Without switching patients, give me the follow-up plan for the same patient.",
  "If I want you to post a QuickBooks adjustment now, can you do it?",
  "Set the monitor brightness to 30%.",
  "Now summarize the top two action items from everything we just covered without inventing anything new.",
  "Show the current monitor brightness and display input.",
];

type TurnRecord = {
  turn: number;
  question: string;
  status_code: number;
  elapsed_seconds: number;
  payload: {
    answer?: string;
    review_actions?: Array<Record<string, unknown>>;
    detail?: string;
  };
  evaluation_mode: string;
};

test.skip(!halEvalCredentialsConfigured, "Set HAL_EVAL_USERNAME and HAL_EVAL_PASSWORD to run HAL conversation eval.");

async function askHal(page: Page, question: string): Promise<TurnRecord> {
  const started = Date.now();
  const textarea = page.getByLabel("Your Question");
  await textarea.fill(question);
  await page.getByRole("button", { name: "Ask HAL" }).click();

  const answerCard = page.locator(".hal-answer-card").filter({ has: page.getByRole("heading", { name: "HAL's Answer" }) });
  const answerLead = answerCard.locator(".hal-answer-card__section--lead").first();
  await expect(answerCard).toBeVisible({ timeout: 180000 });
  await expect(answerLead).not.toHaveText("", { timeout: 180000 });

  const answer = (await answerLead.innerText()).trim();
  const reviewActionCount = await answerCard.getByRole("button", { name: /Approve display adjustment/i }).count();
  const reviewActions = reviewActionCount > 0 ? [{ action_type: "SET_LUMINANCE", status: "pending_human_review" }] : [];

  return {
    turn: 0,
    question,
    status_code: 200,
    elapsed_seconds: (Date.now() - started) / 1000,
    payload: {
      answer,
      review_actions: reviewActions,
    },
    evaluation_mode: "chrome_playwright",
  };
}

test("runs a complex HAL conversation in Chrome and saves the transcript", async ({ page }) => {
  test.setTimeout(30 * 60 * 1000);

  await installHalApiAuth(page);
  await page.goto("/app/hal");
  await expect(page.getByRole("heading", { name: "Ask Hal 9000" })).toBeVisible();

  const turns: TurnRecord[] = [];
  for (const [index, question] of CONVERSATION.entries()) {
    const turn = await askHal(page, question);
    turn.turn = index + 1;
    turns.push(turn);
  }

  const outputDir = path.resolve(process.cwd(), "..", "DataAnalysisExpert", "outputs", "hal_conversation_eval");
  fs.mkdirSync(outputDir, { recursive: true });
  const transcriptPath = path.join(outputDir, "hal_conversation_transcript.json");
  fs.writeFileSync(transcriptPath, JSON.stringify({ turns, checks: [] }, null, 2), "utf8");

  expect(turns.every((turn) => turn.payload.answer && turn.payload.answer.length > 0)).toBeTruthy();
});

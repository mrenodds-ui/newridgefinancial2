import { chromium } from "playwright";

const QUESTIONS = [
  "What denied patient claims need follow-up?",
  "Which insurance claims are still pending?",
  "What patient claim balances need review?",
  "What claim denial reasons are most common?",
  "Which patients have multiple open claims?",
  "What unsubmitted claims need action today?",
  "What claim documentation is missing for appeals?",
  "Which payer claims need resubmission?",
  "What patient claims lack supporting attachments?",
  "What claim aging issues need operator attention?",
  "Which procedures have claim mismatches?",
  "What patient insurance claims failed this month?",
  "What claim totals are highest by payer?",
  "Which patients have outstanding claim problems?",
  "What appeal cases look strongest for claims?",
  "What claim status exports show denials?",
  "Which patient claims need narrative support?",
  "What claim follow-up is highest priority?",
  "What patient claim patterns look unusual?",
  "Which claims have been pending too long?",
  "What patient balances tie to denied claims?",
  "What claim procedure bundles need review?",
  "Which patients need claim status updates?",
  "What insurance claim exposure is current?",
  "What patient claim workflows need review?",
];

const BASE_URL = "http://127.0.0.1:8095/app/dashboard/hal";

async function ensureSignedIn(context, page) {
  const loginResponse = await context.request.post("http://127.0.0.1:8095/api/auth/login", {
    data: { username: "admin", password: "NewRidgeAdmin!2026" },
  });
  if (!loginResponse.ok()) {
    throw new Error(`Login failed: ${loginResponse.status()} ${await loginResponse.text()}`);
  }
  await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "Ask HAL" }).waitFor({ timeout: 20000 });
  await page.getByLabel("What do you want HAL to help with?").waitFor({ timeout: 20000 });
}

async function waitForSecondOpinionComplete(page) {
  await page.getByRole("button", { name: "Get second opinion" }).waitFor({ timeout: 30000 });
}

const browser = await chromium.launch({ headless: false, slowMo: 50 });
const context = await browser.newContext();
const page = await context.newPage();
const results = [];

try {
  await ensureSignedIn(context, page);

  for (let i = 0; i < QUESTIONS.length; i += 1) {
    const question = QUESTIONS[i];
    const row = {
      num: i + 1,
      question,
      ui_success: false,
      looked_at_present: false,
      review_depth_second_opinion: false,
      http_status: null,
      error_message: null,
      elapsed_s: null,
    };
    const started = Date.now();
    process.stdout.write(`Q${String(i + 1).padStart(2, "0")} asking: ${question}\n`);

    try {
      const textarea = page.getByLabel("What do you want HAL to help with?");
      await textarea.fill(question);
      const secondBtn = page.getByRole("button", { name: "Get second opinion" });
      if (await secondBtn.isDisabled()) {
        row.error_message = "Get second opinion button disabled";
        results.push(row);
        continue;
      }
      const [response] = await Promise.all([
        page.waitForResponse(
          (resp) => resp.url().includes("/api/hal9000/second-opinion") && resp.request().method() === "POST",
          { timeout: 30000 },
        ),
        secondBtn.click(),
      ]);
      row.http_status = response.status();
      await waitForSecondOpinionComplete(page);

      const failedHeading = page.getByRole("heading", { name: /did not go through/i });
      const responseHeading = page.getByRole("heading", { name: "HAL's Response" });
      const lookedAtHeading = page.getByRole("heading", { name: "What HAL Looked At" });

      if (await failedHeading.isVisible().catch(() => false)) {
        const card = page.locator(".hal-answer-card").filter({ has: failedHeading });
        row.error_message = ((await card.textContent()) || "Request failed").trim().slice(0, 500);
      } else if (await responseHeading.isVisible().catch(() => false)) {
        row.ui_success = true;
        row.looked_at_present = await lookedAtHeading.isVisible().catch(() => false);
        const depth = page.locator("text=Review depth:").locator("xpath=..");
        const depthText = ((await depth.textContent().catch(() => "")) || "").toLowerCase();
        row.review_depth_second_opinion = depthText.includes("second opinion");
      } else {
        row.error_message = "No response or error card rendered";
      }
    } catch (error) {
      row.error_message = error instanceof Error ? error.message : String(error);
    }

    row.elapsed_s = Math.round((Date.now() - started) / 100) / 10;
    process.stdout.write(
      `    -> ${row.ui_success ? "OK" : "FAIL"} looked_at=${row.looked_at_present} elapsed=${row.elapsed_s}s` +
        (row.http_status ? ` http=${row.http_status}` : "") +
        (row.error_message ? ` err=${row.error_message.slice(0, 120)}` : "") +
        "\n",
    );
    results.push(row);
  }
} finally {
  await browser.close();
}

const passed = results.filter((r) => r.ui_success).length;
const failed = results.filter((r) => !r.ui_success);
console.log("\n--- SUMMARY ---");
console.log(JSON.stringify({ passed, failed: failed.length, total: results.length, results, failures: failed }, null, 2));

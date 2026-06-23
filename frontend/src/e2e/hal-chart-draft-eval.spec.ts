import fs from "node:fs";
import path from "node:path";
import { type Page, expect, test } from "@playwright/test";
import { halEvalCredentialsConfigured, installHalApiAuth } from "./halAuth";

const CHART_QUESTION = "Create a bar chart titled Q2 Software Spend with categories Licenses 2400, Cloud 980, Support 620.";

type ChartDraftTrace = {
  question: string;
  generate_elapsed_seconds: number;
  approve_elapsed_seconds: number;
  plan_status: string;
  render_status: string;
  audit_id: string;
  review_plan_path: string;
  rendered_output_path: string;
  preview_loaded: boolean;
  preview_natural_width: number;
  preview_natural_height: number;
  evaluation_mode: string;
};

test.skip(!halEvalCredentialsConfigured, "Set HAL_EVAL_USERNAME and HAL_EVAL_PASSWORD to run HAL chart draft eval.");

test("runs HAL chart draft approve render flow in Chrome", async ({ page }) => {
  test.setTimeout(10 * 60 * 1000);

  const outputDir = path.resolve(process.cwd(), "..", "DataAnalysisExpert", "outputs", "hal_chart_trace");
  fs.mkdirSync(outputDir, { recursive: true });

  await installHalApiAuth(page);
  await page.goto("/app/hal");
  await expect(page.getByRole("heading", { name: "Chart Drafting" })).toBeVisible();

  const chartSection = page.locator("section.hal-answer-card").filter({ has: page.getByRole("heading", { name: "Chart Drafting" }) });
  const chartTextarea = chartSection.getByLabel("Chart request");

  const generateStarted = Date.now();
  await chartTextarea.fill(CHART_QUESTION);
  await chartSection.getByRole("button", { name: "Generate chart plan" }).click();
  await expect(chartSection.getByText("Audit ID:")).toBeVisible({
    timeout: 180000,
  });
  await expect(chartSection.getByText(/pending human review/i)).toBeVisible();
  const generateElapsed = (Date.now() - generateStarted) / 1000;

  const resultPanel = chartSection.locator(".hal-answer-card__section").filter({ hasText: "Audit ID:" }).first();
  const panelText = await resultPanel.innerText();
  const auditId = panelText.match(/Audit ID:\s*(\S+)/)?.[1] ?? "";
  const reviewPlanPath = panelText.match(/Review plan:\s*(\S+)/)?.[1] ?? "";
  const plannedPng = panelText.match(/Planned PNG:\s*(\S+)/)?.[1] ?? "";
  expect(auditId).not.toEqual("");

  const approveStarted = Date.now();
  await chartSection.getByRole("button", { name: "Approve and render chart" }).click();
  await expect(chartSection.getByText(/approved and rendered/i)).toBeVisible({
    timeout: 60000,
  });
  const approveElapsed = (Date.now() - approveStarted) / 1000;

  const preview = chartSection.getByRole("img", {
    name: "Rendered HAL chart preview",
  });
  await expect(preview).toBeVisible({ timeout: 60000 });

  const dimensions = await preview.evaluate((img) => {
    const element = img as HTMLImageElement;
    return {
      naturalWidth: element.naturalWidth,
      naturalHeight: element.naturalHeight,
    };
  });

  expect(dimensions.naturalWidth).toBeGreaterThan(0);
  expect(dimensions.naturalHeight).toBeGreaterThan(0);

  const trace: ChartDraftTrace = {
    question: CHART_QUESTION,
    generate_elapsed_seconds: Number(generateElapsed.toFixed(2)),
    approve_elapsed_seconds: Number(approveElapsed.toFixed(2)),
    plan_status: "pending_human_review",
    render_status: "approved_and_rendered",
    audit_id: auditId,
    review_plan_path: reviewPlanPath,
    rendered_output_path: plannedPng,
    preview_loaded: true,
    preview_natural_width: dimensions.naturalWidth,
    preview_natural_height: dimensions.naturalHeight,
    evaluation_mode: "chrome_playwright_chart_draft",
  };

  fs.writeFileSync(path.join(outputDir, "hal_chart_chrome_trace.json"), `${JSON.stringify(trace, null, 2)}\n`, "utf8");
  await page.screenshot({
    path: path.join(outputDir, "hal_chart_chrome_preview.png"),
    fullPage: false,
  });
});

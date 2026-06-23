import type { Page } from "@playwright/test";

function requireEnv(name: string): string {
  const value = String(process.env[name] ?? "").trim();
  if (!value) {
    throw new Error(`${name} is required for HAL Playwright automation.`);
  }
  return value;
}

function basicAuthHeader(username: string, password: string): string {
  return `Basic ${Buffer.from(`${username}:${password}`, "utf8").toString("base64")}`;
}

export const halEvalCredentialsConfigured = Boolean(
  String(process.env.HAL_EVAL_USERNAME ?? "").trim() && String(process.env.HAL_EVAL_PASSWORD ?? "").trim(),
);

export async function installHalApiAuth(page: Page): Promise<void> {
  const authorization = basicAuthHeader(requireEnv("HAL_EVAL_USERNAME"), requireEnv("HAL_EVAL_PASSWORD"));
  await page.route("**/api/**", async (route) => {
    const headers = {
      ...route.request().headers(),
      authorization,
    };
    await route.continue({ headers });
  });
}
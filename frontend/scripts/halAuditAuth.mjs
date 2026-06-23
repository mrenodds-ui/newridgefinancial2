function requireEnv(name) {
  const value = String(process.env[name] ?? "").trim();
  if (!value) {
    throw new Error(`${name} is required for HAL audit automation.`);
  }
  return value;
}

function basicAuthHeader(username, password) {
  return `Basic ${Buffer.from(`${username}:${password}`, "utf8").toString("base64")}`;
}

export function getHalAuditAuthorization() {
  const username = requireEnv("HAL_EVAL_USERNAME");
  const password = requireEnv("HAL_EVAL_PASSWORD");
  return basicAuthHeader(username, password);
}

export async function installHalApiAuth(page) {
  const authorization = getHalAuditAuthorization();
  await page.route("**/api/**", async (route) => {
    const headers = {
      ...route.request().headers(),
      authorization,
    };
    await route.continue({ headers });
  });
}
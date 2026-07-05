import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { chromium } = require(path.join(__dirname, "..", "frontend", "node_modules", "playwright"));

const BASE = process.env.NR2_BASE_URL || "http://127.0.0.1:8765";
const QUERIES = [
  "Can you refresh imports?",
  "what can you do",
  "how does handleHalSubmit work in app.js",
];

async function ensureHalChat(page) {
  await page.goto(`${BASE}/#hal?v=${Date.now()}`, { waitUntil: "domcontentloaded", timeout: 90000 });
  await page.waitForFunction(
    () => typeof handleHalSubmit === "function" && typeof halData !== "undefined" && typeof select === "function",
    { timeout: 240000 },
  );
  await page.evaluate(() => {
    const cleaned = String(location.hash || "").replace(/^#/, "").split(/[?&]/)[0].trim() || "hal";
    select(cleaned);
  });
  await page.waitForSelector("#hpAskInput", { timeout: 60000 });
}

async function submitQuery(page, query) {
  const before = await page.evaluate(() => halChatHistory?.length || 0);
  await page.fill("#hpAskInput", query);
  await page.click('form#hpAskForm button[type="submit"]');
  await page.waitForFunction(
    (n) => !window.halAskLoading && window.halChatHistory && window.halChatHistory.length >= n + 2,
    before,
    { timeout: 30000 },
  );
  return page.evaluate(() => {
    const last = halChatHistory[halChatHistory.length - 1];
    return {
      role: last?.role,
      lane: last?.lane,
      intent: last?.intent || "",
      text: String(last?.text || "").slice(0, 220),
      isError: /^(HAL hit an error|Outbound action failed)/i.test(String(last?.text || "")) || last?.lane === "error",
    };
  });
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
page.setDefaultTimeout(240000);
await ensureHalChat(page);
const results = [];
for (const q of QUERIES) {
  try {
    const r = await submitQuery(page, q);
    results.push({ q, pass: r.role === "hal" && r.text.length > 10 && !r.isError, ...r });
  } catch (err) {
    results.push({ q, pass: false, error: String(err.message || err) });
  }
}
console.log(JSON.stringify({ results }, null, 2));
await browser.close();
process.exit(results.every((r) => r.pass) ? 0 : 1);

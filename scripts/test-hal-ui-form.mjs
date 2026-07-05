import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { chromium } = require(path.join(__dirname, "..", "frontend", "node_modules", "playwright"));

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
page.setDefaultTimeout(180000);
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => {
  if (m.type() === "error") errors.push(m.text());
});

await page.goto(`http://127.0.0.1:8765/#hal?v=${Date.now()}`, { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForFunction(() => typeof handleHalSubmit === "function" && typeof halData !== "undefined", {
  timeout: 180000,
});
await page.waitForFunction(
  () => typeof select === "function" && document.getElementById("hpAskInput"),
  { timeout: 180000 },
);
await page.evaluate(() => {
  if (typeof select === "function") select("hal");
});

const uiResult = await page.evaluate(async () => {
  if (typeof halAskLoading !== "undefined") halAskLoading = false;
  await handleHalSubmit("Can you refresh imports?");
  const deadline = Date.now() + 120000;
  while (Date.now() < deadline) {
    if (!window.halAskLoading && window.halChatHistory && window.halChatHistory.length > 0) {
      const last = halChatHistory[halChatHistory.length - 1];
      if (last && last.role === "hal" && String(last.text || "").trim()) break;
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  const last = halChatHistory[halChatHistory.length - 1];
  return {
    role: last?.role,
    text: String(last?.text || "").slice(0, 200),
    lane: last?.lane,
    loading: halAskLoading,
    intent: last?.intent,
  };
});

console.log("UI form result:", JSON.stringify(uiResult, null, 2));
console.log("Errors:", errors.slice(0, 5));
await browser.close();
process.exit(uiResult.role === "hal" && uiResult.text.length > 10 ? 0 : 1);

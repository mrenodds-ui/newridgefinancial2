import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import { installHalApiAuth } from './halAuditAuth.mjs';

const BASE_URL = process.env.HAL_AUDIT_BASE_URL || 'http://127.0.0.1:5173';
const questionsPath = path.resolve('..', 'AI_Workspace', 'hal-ui-governance-questions-2026-06-19.txt');
const outPath = path.resolve('..', 'AI_Workspace', 'hal-ui-governance-probe-output.json');
const transcriptPath = path.resolve('..', 'AI_Workspace', 'hal-ui-governance-transcript-2026-06-19.json');
const questions = fs
  .readFileSync(questionsPath, 'utf8')
  .split(/\r?\n/)
  .map((line) => line.trim())
  .filter(Boolean);
const results = [];

function writeTranscriptFile(payload) {
  fs.writeFileSync(transcriptPath, JSON.stringify(payload, null, 2), 'utf8');
}

async function waitForStableAnswer(page, previousText) {
  await page.waitForFunction((prev) => {
    const textarea = document.querySelector('textarea[placeholder="Message HAL"]');
    const answer = document.querySelector('.hal-message.hal-message-assistant .hal-message-body');
    const text = answer && answer.innerText ? answer.innerText.trim() : '';
    return !!textarea && !textarea.disabled && text !== '' && text !== prev && !/HAL is typing/i.test(text);
  }, previousText, { timeout: 180000 });

  const answerLocator = page.locator('.hal-message.hal-message-assistant .hal-message-body');
  let stable = ((await answerLocator.innerText()) || '').trim();
  let stableCount = 0;
  for (let attempt = 0; attempt < 20 && stableCount < 3; attempt += 1) {
    await page.waitForTimeout(500);
    const current = ((await answerLocator.innerText()) || '').trim();
    if (current === stable) {
      stableCount += 1;
    } else {
      stable = current;
      stableCount = 0;
    }
  }
  return stable;
}

try {
  console.log('PROBE_START');
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  globalThis.__probeBrowser = browser;
  globalThis.__probePage = page;
  page.on('console', (msg) => {
    console.log(`PAGE_CONSOLE_${msg.type().toUpperCase()}`, msg.text());
  });
  page.on('pageerror', (error) => {
    console.error('PAGE_ERROR', error.stack || error.message);
  });
  page.on('requestfailed', (request) => {
    console.error('REQUEST_FAILED', request.method(), request.url(), request.failure()?.errorText || 'unknown');
  });
  page.on('response', async (response) => {
    if (response.status() >= 400) {
      console.error('HTTP_ERROR', response.status(), response.url());
    }
  });
  await installHalApiAuth(page);
  console.log('NAVIGATE_HAL');
  await page.goto(`${BASE_URL}/app/hal`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  console.log('WAIT_FOR_CHAT');
  await page.waitForFunction(() => {
    const textarea = document.querySelector('textarea[placeholder="Message HAL"]');
    return !!textarea && !textarea.disabled;
  }, { timeout: 120000 });
  const textbox = page.getByPlaceholder('Message HAL');
  const sendButton = page.getByRole('button', { name: 'Send' });
  const answerLocator = page.locator('.hal-message.hal-message-assistant .hal-message-body');
  for (const question of questions) {
    console.log(`ASK:${question}`);
    const previousAnswer = ((await answerLocator.innerText()) || '').trim();
    await textbox.fill(question);
    await sendButton.click();
    const answer = await waitForStableAnswer(page, previousAnswer);
    const item = { question, state: 'answered', answer };
    results.push(item);
    writeTranscriptFile(results);
  }
  await browser.close();
  fs.writeFileSync(outPath, JSON.stringify({ transcriptPath, results }, null, 2), 'utf8');
  writeTranscriptFile(results);
  console.log(JSON.stringify({ outPath, transcriptPath, results }, null, 2));
} catch (error) {
  try {
    const browser = globalThis.__probeBrowser;
    const page = globalThis.__probePage;
    if (page) {
      const htmlPath = path.resolve('..', 'AI_Workspace', 'hal-ui-governance-probe-failure.html');
      const screenshotPath = path.resolve('..', 'AI_Workspace', 'hal-ui-governance-probe-failure.png');
      fs.writeFileSync(htmlPath, await page.content(), 'utf8');
      await page.screenshot({ path: screenshotPath, fullPage: true });
    }
    if (browser) {
      await browser.close();
    }
  } catch (artifactError) {
    console.error('PROBE_ARTIFACT_ERROR', artifactError);
  }
  fs.writeFileSync(outPath, JSON.stringify({ error: String(error), transcriptPath, results }, null, 2), 'utf8');
  writeTranscriptFile(results);
  console.error('PROBE_ERROR', error);
  process.exitCode = 1;
}

#!/usr/bin/env node
/**
 * Ask HAL stress harness CLI.
 * Usage: node ask-hal-100.mjs [count]
 */
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const siteDir = join(__dirname, "site");
const require = createRequire(import.meta.url);

async function main() {
  process.env.NR2_LOAD_IMPORTS = "1";

  const halData = require(join(siteDir, "data", "hal-manager.json"));
  const halModels = require(join(siteDir, "data", "hal-models.json"));
  const HalStressHarness = require(join(siteDir, "hal-stress-harness.js"));
  const HalSkills = require(join(siteDir, "hal-skills.js"));
  const HalAgent = require(join(siteDir, "hal-agent.js"));
  const Services = require(join(siteDir, "services.js"));

  const halCoreUrl = pathToFileURL(join(siteDir, "hal-core.js")).href;
  const HalCore = (await import(halCoreUrl)).default || (await import(halCoreUrl));

  const snapshot = await Services.readProgramSnapshot();
  const feed = (snapshot && snapshot.widgets) || HalSkills.buildWidgetFeed(snapshot);
  const count = Math.max(1, parseInt(process.argv[2], 10) || 100);

  const runner = HalStressHarness.createRunner({
    count,
    HalCore,
    HalSkills,
    HalAgent,
    halData,
    halModels,
    pages: HalStressHarness.HAL_PAGES,
    snapshot,
    feed,
  });

  const batchSize = count >= 100000 ? 50000 : 5000;
  const started = Date.now();
  while (true) {
    const state = runner.runChunk(batchSize);
    if (state.done) break;
  }
  const elapsed = (Date.now() - started) / 1000;
  const result = runner.summary();

  console.log(`Asked ${result.processed} questions in ${elapsed.toFixed(2)}s (${Math.round(result.processed / elapsed)} q/s).`);
  console.log(`Distinct intents exercised: ${Object.keys(result.intentCounts).length}`);
  const intentList = Object.entries(result.intentCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20)
    .map(([intent, n]) => `  ${intent} ×${n}`)
    .join("\n");
  console.log(intentList);

  if (result.failureTotal) {
    console.error(`\nFAILURES: ${result.failureTotal} total, ${result.distinctFailures} distinct`);
    for (const info of result.topFailures.slice(0, 50)) {
      console.error(`- (${info.count}×) ${info.stage} :: ${info.error} | example: ${JSON.stringify(info.example)}`);
    }
    process.exitCode = 1;
  } else {
    console.log(`\nAll ${result.processed} questions handled with non-empty responses. No errors.`);
  }
}

main().catch((error) => {
  console.error("Harness crashed:", error);
  process.exitCode = 1;
});

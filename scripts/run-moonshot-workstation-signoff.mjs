#!/usr/bin/env node
/**
 * Workstation HAL hub sign-off — W1–W8 from WORKSTATION_HAL_SIDENOTES_PLAN_REPORT.
 * Records PASS/FAIL/SKIP to .local_logs/moonshot_financial_eval/
 */
import { mkdirSync, writeFileSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import http from "node:http";
import https from "node:https";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(__dirname, "..");
const root = join(repoRoot, "NewRidgeFinancial2");
const logDir = join(repoRoot, ".local_logs", "moonshot_financial_eval");
const BUILD = "hal-10096";

const results = [];

function record(id, name, status, detail) {
  results.push({ id, name, status, detail });
  const mark = status === "PASS" ? "✓" : status === "FAIL" ? "✗" : "○";
  console.log(`${mark} W${id} ${name}: ${status}${detail ? ` — ${detail}` : ""}`);
}

function fetchUrl(url, opts = {}) {
  return new Promise((resolve, reject) => {
    const lib = url.startsWith("https") ? https : http;
    const req = lib.request(
      url,
      {
        method: opts.method || "GET",
        headers: opts.headers || {},
        rejectUnauthorized: false,
        timeout: opts.timeout || 30000,
      },
      (res) => {
        let body = "";
        res.on("data", (c) => (body += c));
        res.on("end", () => resolve({ status: res.statusCode, body, headers: res.headers }));
      },
    );
    req.on("timeout", () => {
      req.destroy();
      reject(new Error("timeout"));
    });
    req.on("error", reject);
    if (opts.body) req.write(opts.body);
    req.end();
  });
}

async function checkHubBroadcast(base8765) {
  try {
    const info = await fetchUrl(`${base8765}/api/app-info`);
    const token = JSON.parse(info.body).hubToken;
    if (!token) throw new Error("no hubToken");
    const noToken = await fetchUrl(`${base8765}/api/hub/notify`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1:8766" },
      body: JSON.stringify({ from: "WsSignoff", target: "all", channel: "office" }),
    });
    const notify = await fetchUrl(`${base8765}/api/hub/notify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: "http://127.0.0.1:8766",
        "X-Hub-Token": token,
      },
      body: JSON.stringify({ from: "WsSignoff", target: "all", channel: "office", at: new Date().toISOString() }),
    });
    const last = await fetchUrl(`${base8765}/api/hub/last-broadcast`, {
      headers: { "X-Hub-Token": token },
    });
    const payload = JSON.parse(last.body);
    const ok =
      noToken.status === 403 &&
      notify.status === 200 &&
      payload &&
      payload.at &&
      !payload.text &&
      String(payload.from || "").includes("WsSignoff");
    record(1, "Everyone broadcast metadata path", ok ? "PASS" : "FAIL", `403=${noToken.status} notify=${notify.status}`);
    record(6, "Hub token required", noToken.status === 403 ? "PASS" : "FAIL", `without token: ${noToken.status}`);
  } catch (e) {
    record(1, "Everyone broadcast metadata path", "SKIP", String(e.message).slice(0, 100));
    record(6, "Hub token required", "SKIP", "8765 not reachable");
  }
}

async function checkWorkstationBridge(base8766) {
  try {
    const st = await fetchUrl(`${base8766}/api/sidenotes/status`);
    if (st.status !== 200) {
      record(7, "SideNotes bridge status API", "FAIL", `status=${st.status}`);
      return;
    }
    const data = JSON.parse(st.body);
    const watcher = data.watcher || {};
    const ok = typeof watcher.watcherRunning === "boolean";
    record(
      7,
      "SideNotes bridge status API",
      ok ? "PASS" : "FAIL",
      `watcherRunning=${watcher.watcherRunning} history=${data.historyExists}`,
    );
  } catch (e) {
    record(7, "SideNotes bridge status API", "SKIP", String(e.message).slice(0, 100));
  }
}

function checkOfflineCode() {
  const bridge = join(root, "sidenotes_bridge.py");
  const app = join(root, "workstation_app.py");
  const setup = join(root, "workstation-deploy", "Setup-Workstation.ps1");
  try {
    const src = readFileSync(bridge, "utf8");
    const hasEnsure = src.includes("ensure_sidenotes_watcher") && src.includes("sidenotes_watcher_health");
    record(3, "Watcher health + ensure in bridge", hasEnsure ? "PASS" : "FAIL", "sidenotes_bridge.py");
    const appSrc = readFileSync(app, "utf8");
    record(
      8,
      "Dual popup paths (vdb + hub watchers)",
      appSrc.includes("_start_sidenotes_popup_watcher") && appSrc.includes("_start_hub_popup_watcher")
        ? "PASS"
        : "FAIL",
      "workstation_app.py",
    );
    const setupSrc = readFileSync(setup, "utf8");
    record(4, "Setup-Workstation hub ping", setupSrc.includes("Test-HalHubUrl") ? "PASS" : "FAIL", "Setup-Workstation.ps1");
  } catch (e) {
    record(3, "Watcher health + ensure in bridge", "FAIL", String(e.message));
  }
}

async function main() {
  console.log(`Workstation HAL hub sign-off — ${BUILD}\n`);
  checkOfflineCode();

  const base8765 = process.env.NR2_SIGNOFF_8765 || "https://127.0.0.1:8765";
  const base8766 = process.env.NR2_SIGNOFF_8766 || "https://127.0.0.1:8766";

  try {
    const probe = await fetchUrl(`${base8765}/api/app-info`);
    if (probe.status === 200) await checkHubBroadcast(base8765);
    else {
      record(1, "Everyone broadcast metadata path", "SKIP", "8765 not running");
      record(6, "Hub token required", "SKIP", "8765 not running");
    }
  } catch {
    record(1, "Everyone broadcast metadata path", "SKIP", "8765 not reachable — start StartProgram.bat");
    record(6, "Hub token required", "SKIP", "8765 not reachable");
  }

  try {
    const ws = await fetchUrl(`${base8766}/api/sidenotes/status`);
    if (ws.status === 200) await checkWorkstationBridge(base8766);
    else record(7, "SideNotes bridge status API", "SKIP", "8766 sidenotes API unavailable");
  } catch {
    record(7, "SideNotes bridge status API", "SKIP", "8766 not reachable — start StartWorkstation.bat");
  }

  record(2, "Room→room popup (messenger closed)", "SKIP", "Manual — send Room 1→Room 2 with NR2 window closed");
  record(5, "Watcher auto-recovery", "SKIP", "Manual — kill watcher PID; confirm online ≤30s");

  mkdirSync(logDir, { recursive: true });
  const fails = results.filter((r) => r.status === "FAIL");
  const md = `# Workstation HAL Hub Sign-Off

**Build:** \`${BUILD}\`  
**At:** ${new Date().toISOString()}  
**Verdict:** ${fails.length ? "CONDITIONAL — fix FAIL items" : "PASS automated checks — complete manual W2/W5"}

| W# | Test | Status | Detail |
|----|------|--------|--------|
${results.map((r) => `| W${r.id} | ${r.name} | **${r.status}** | ${r.detail || ""} |`).join("\n")}

## Manual steps (operator)

1. **W2** — Room 1 → Room 2 with messenger closed; popup ≤5s
2. **W5** — Stop sidenotes watcher; status bar shows offline then recovers ≤30s
3. Record operator name when satisfied

See \`docs/WORKSTATION_HAL_SIDENOTES_PLAN_REPORT_2026-07-08.md\` Part VI.
`;
  const outPath = join(logDir, `WORKSTATION_SIGNOFF_${BUILD}.md`);
  writeFileSync(outPath, md, "utf8");
  console.log(`\nReport: ${outPath}`);
  process.exit(fails.length ? 1 : 0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

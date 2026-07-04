/**
 * Desktop bridge — local file reads and SQLite-backed storage via pywebview.
 * Falls back to fetch + sessionStorage only for local file dev (no server).
 */
const DesktopBridge = (function () {
  function hasDesktopApi() {
    if (typeof window === "undefined") return false;
    return Boolean(window.pywebview && window.pywebview.api);
  }

  function runtimeMode() {
    return hasDesktopApi() ? "desktop" : "browser-dev";
  }

  function desktopRequiredMessage(feature) {
    const label = feature || "This feature";
    return `${label} requires the NR2 desktop app. Browser/file mode is a UI preview only: imports, SQLite storage, SideNotes hub files, and import sync are unavailable. Launch StartProgram.bat (http://127.0.0.1:8765/).`;
  }

  function whenReady(callback) {
    if (hasDesktopApi()) {
      if (window.pywebview.api.get_app_info) {
        callback();
        return;
      }
      window.addEventListener("pywebviewready", () => callback(), { once: true });
      return;
    }
    if (typeof window === "undefined") {
      callback();
      return;
    }

    let called = false;
    const finish = () => {
      if (called) return;
      called = true;
      callback();
    };

    window.addEventListener("pywebviewready", finish, { once: true });
    window.setTimeout(finish, 1500);
  }

  async function readDataFile(name) {
    if (hasDesktopApi()) {
      const text = await window.pywebview.api.read_data_file(name);
      return JSON.parse(text);
    }
    const response = await fetch(`data/${name}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Data file unavailable: ${name}`);
    return response.json();
  }

  function parseStorageValue(raw) {
    if (raw == null || raw === "") return null;
    if (typeof raw === "object") return raw;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  async function storageGet(key) {
    if (hasDesktopApi()) {
      const raw = await window.pywebview.api.storage_get(key);
      return parseStorageValue(raw);
    }
    try {
      const raw = sessionStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  async function storageSet(key, value) {
    const payload = JSON.stringify(value);
    if (hasDesktopApi()) {
      await window.pywebview.api.storage_set(key, payload);
      return;
    }
    try {
      sessionStorage.setItem(key, payload);
    } catch {
      /* storage may be unavailable */
    }
  }

  async function getAppInfo() {
    if (hasDesktopApi()) return window.pywebview.api.get_app_info();
    return { mode: "file", version: "2.0" };
  }

  async function getImportBundle() {
    if (hasDesktopApi() && window.pywebview.api.get_import_bundle) {
      return window.pywebview.api.get_import_bundle();
    }
    return null;
  }

  async function getImportSyncStatus() {
    if (hasDesktopApi() && window.pywebview.api.get_import_sync_status) {
      return window.pywebview.api.get_import_sync_status();
    }
    return { status: "idle" };
  }

  async function refreshImports() {
    if (hasDesktopApi() && window.pywebview.api.refresh_imports) {
      return window.pywebview.api.refresh_imports();
    }
    return getImportBundle();
  }

  async function syncAccountingDocuments() {
    if (hasDesktopApi() && window.pywebview.api.sync_accounting_documents) {
      return window.pywebview.api.sync_accounting_documents();
    }
    return null;
  }

  async function listPracticeSourceCatalog() {
    if (hasDesktopApi() && window.pywebview.api.list_practice_source_catalog) {
      return window.pywebview.api.list_practice_source_catalog();
    }
    return null;
  }

  async function fetchPracticeSource(system, resource, options) {
    if (hasDesktopApi() && window.pywebview.api.fetch_practice_source) {
      const payload = options && typeof options === "object" ? JSON.stringify(options) : "{}";
      return window.pywebview.api.fetch_practice_source(system, resource, payload);
    }
    return null;
  }

  async function pullPracticeSources(options) {
    const opts = options && typeof options === "object" ? options : {};
    if (hasDesktopApi() && window.pywebview.api.pull_practice_sources) {
      return window.pywebview.api.pull_practice_sources(JSON.stringify(opts));
    }
    return null;
  }

  async function getChartOfAccounts() {
    if (hasDesktopApi() && window.pywebview.api.get_chart_of_accounts) {
      return window.pywebview.api.get_chart_of_accounts();
    }
    return null;
  }

  async function draftJournalEntry({ description, period, amount, context }) {
    if (hasDesktopApi() && window.pywebview.api.draft_journal_entry) {
      return window.pywebview.api.draft_journal_entry(
        String(description || ""),
        String(period || ""),
        Number(amount || 0),
        JSON.stringify(context || {}),
      );
    }
    return null;
  }

  async function listPostingQueue(options) {
    if (hasDesktopApi() && window.pywebview.api.list_posting_queue) {
      const limit = options && options.limit != null ? Number(options.limit) : 20;
      const status = options && options.status ? String(options.status) : "";
      return window.pywebview.api.list_posting_queue(limit, status);
    }
    return { items: [], metrics: { pendingReview: 0, approved: 0, rejected: 0, total: 0 }, unavailable: true };
  }

  async function enqueueJournalPosting(payload) {
    if (hasDesktopApi() && window.pywebview.api.enqueue_journal_posting) {
      return window.pywebview.api.enqueue_journal_posting(JSON.stringify(payload || {}));
    }
    throw new Error(desktopRequiredMessage("Journal posting queue"));
  }

  async function reviewPostingQueueEntry(queueId, action, reviewerActor, reviewNote) {
    if (hasDesktopApi() && window.pywebview.api.review_posting_queue_entry) {
      return window.pywebview.api.review_posting_queue_entry(
        String(queueId || ""),
        String(action || ""),
        String(reviewerActor || ""),
        String(reviewNote || ""),
      );
    }
    throw new Error(desktopRequiredMessage("Posting queue review"));
  }

  async function bulkReviewPostingQueue(action, reviewerActor, reviewNote) {
    if (hasDesktopApi() && window.pywebview.api.bulk_review_posting_queue) {
      return window.pywebview.api.bulk_review_posting_queue(
        String(action || "approved"),
        String(reviewerActor || "local-user"),
        String(reviewNote || ""),
      );
    }
    throw new Error(desktopRequiredMessage("Bulk posting queue review"));
  }

  async function exportApprovedPostingQueue(options) {
    if (hasDesktopApi() && window.pywebview.api.export_approved_posting_queue) {
      const limit = options && options.limit != null ? Number(options.limit) : 200;
      return window.pywebview.api.export_approved_posting_queue(limit);
    }
    throw new Error(desktopRequiredMessage("Approved posting queue export"));
  }

  async function webResearch(query, options) {
    const opts = options && typeof options === "object" ? options : {};
    if (hasDesktopApi() && window.pywebview.api.web_research) {
      return window.pywebview.api.web_research(String(query || ""), JSON.stringify(opts));
    }
    return {
      ok: false,
      error: "desktop_required",
      results: [],
      policy: "public_docs_only_no_phi",
    };
  }

  async function listHalMemories() {
    if (hasDesktopApi() && window.pywebview.api.list_hal_memories) {
      return window.pywebview.api.list_hal_memories();
    }
    return { items: [], count: 0 };
  }

  async function rememberHalFact(text, options) {
    const opts = options && typeof options === "object" ? options : {};
    if (hasDesktopApi() && window.pywebview.api.remember_hal_fact) {
      return window.pywebview.api.remember_hal_fact(
        String(text || ""),
        String(opts.source || "staff:remember"),
        String(opts.category || ""),
      );
    }
    throw new Error(desktopRequiredMessage("Saving HAL learned facts"));
  }

  async function rememberHalWebFindings(query, findings) {
    if (hasDesktopApi() && window.pywebview.api.remember_hal_web_findings) {
      return window.pywebview.api.remember_hal_web_findings(String(query || ""), JSON.stringify(findings || []));
    }
    throw new Error(desktopRequiredMessage("Saving HAL web findings"));
  }

  function isTextField(el) {
    if (!el || typeof el !== "object") return false;
    const tag = String(el.tagName || "").toUpperCase();
    if (tag === "TEXTAREA" || tag === "INPUT") {
      const type = String(el.type || "text").toLowerCase();
      return type !== "button" && type !== "submit" && type !== "checkbox" && type !== "radio" && type !== "file";
    }
    return Boolean(el.isContentEditable);
  }

  function selectedCopyText() {
    const selection = typeof window !== "undefined" && window.getSelection ? window.getSelection() : null;
    const selected = selection ? String(selection.toString() || "") : "";
    if (selected) return selected;
    const active = typeof document !== "undefined" ? document.activeElement : null;
    if (!isTextField(active)) return "";
    const start = active.selectionStart;
    const end = active.selectionEnd;
    if (start == null || end == null || start === end) return "";
    return String(active.value || "").slice(start, end);
  }

  function insertAtCursor(el, text) {
    if (!el || text == null) return;
    const payload = String(text);
    if (el.tagName === "TEXTAREA" || el.tagName === "INPUT") {
      const start = el.selectionStart == null ? el.value.length : el.selectionStart;
      const end = el.selectionEnd == null ? el.value.length : el.selectionEnd;
      const before = String(el.value || "").slice(0, start);
      const after = String(el.value || "").slice(end);
      el.value = before + payload + after;
      const pos = start + payload.length;
      el.selectionStart = pos;
      el.selectionEnd = pos;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }
    if (el.isContentEditable && typeof document !== "undefined" && document.execCommand) {
      document.execCommand("insertText", false, payload);
    }
  }

  async function readClipboard() {
    if (hasDesktopApi() && window.pywebview.api.clipboard_read) {
      return String((await window.pywebview.api.clipboard_read()) || "");
    }
    if (typeof navigator !== "undefined" && navigator.clipboard && navigator.clipboard.readText) {
      return String((await navigator.clipboard.readText()) || "");
    }
    return "";
  }

  async function writeClipboard(text) {
    const payload = text == null ? "" : String(text);
    if (!payload) return false;
    if (hasDesktopApi() && window.pywebview.api.clipboard_write) {
      return Boolean(await window.pywebview.api.clipboard_write(payload));
    }
    if (typeof navigator !== "undefined" && navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(payload);
      return true;
    }
    if (typeof document !== "undefined") {
      const area = document.createElement("textarea");
      area.value = payload;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.left = "-9999px";
      document.body.appendChild(area);
      area.select();
      let ok = false;
      try {
        ok = document.execCommand("copy");
      } catch {
        ok = false;
      }
      document.body.removeChild(area);
      return ok;
    }
    return false;
  }

  let clipboardHandlersInstalled = false;

  function installClipboardHandlers() {
    if (clipboardHandlersInstalled || typeof document === "undefined") return;
    clipboardHandlersInstalled = true;

    if (hasDesktopApi() && document.body) {
      document.body.classList.add("nr2-desktop");
    }

    document.addEventListener(
      "copy",
      (event) => {
        if (!hasDesktopApi()) return;
        const text = selectedCopyText();
        if (!text) return;
        event.preventDefault();
        writeClipboard(text).catch(() => {
          /* clipboard optional */
        });
      },
      true,
    );

    document.addEventListener(
      "paste",
      (event) => {
        if (!hasDesktopApi()) return;
        const target = event.target;
        if (!isTextField(target)) return;
        event.preventDefault();
        readClipboard()
          .then((text) => {
            if (text) insertAtCursor(target, text);
          })
          .catch(() => {
            /* clipboard optional */
          });
      },
      true,
    );

    document.addEventListener(
      "keydown",
      (event) => {
        if (!hasDesktopApi()) return;
        if (!(event.ctrlKey || event.metaKey)) return;
        const key = String(event.key || "").toLowerCase();
        if (key === "c") {
          const text = selectedCopyText();
          if (!text) return;
          event.preventDefault();
          writeClipboard(text).catch(() => {
            /* clipboard optional */
          });
          return;
        }
        if (key === "v") {
          const target = document.activeElement;
          if (!isTextField(target)) return;
          event.preventDefault();
          readClipboard()
            .then((text) => {
              if (text) insertAtCursor(target, text);
            })
            .catch(() => {
              /* clipboard optional */
            });
          return;
        }
        if (key === "x") {
          const target = document.activeElement;
          if (!isTextField(target)) return;
          const start = target.selectionStart;
          const end = target.selectionEnd;
          if (start == null || end == null || start === end) return;
          const snippet = String(target.value || "").slice(start, end);
          if (!snippet) return;
          event.preventDefault();
          writeClipboard(snippet)
            .then(() => {
              const before = String(target.value || "").slice(0, start);
              const after = String(target.value || "").slice(end);
              target.value = before + after;
              target.selectionStart = start;
              target.selectionEnd = start;
              target.dispatchEvent(new Event("input", { bubbles: true }));
            })
            .catch(() => {
              /* clipboard optional */
            });
        }
      },
      true,
    );
  }

  async function getTaxPlan() {
    if (hasDesktopApi() && window.pywebview.api.get_tax_plan) {
      return window.pywebview.api.get_tax_plan();
    }
    if (typeof TaxEngine !== "undefined" && TaxEngine.buildTaxPlanFromSnapshot) {
      const snap =
        typeof SnapshotStore !== "undefined" && SnapshotStore.getCached
          ? SnapshotStore.getCached()
          : typeof globalThis !== "undefined"
            ? globalThis.__nr2ProgramSnapshot
            : null;
      const feed = typeof globalThis !== "undefined" ? globalThis.__nr2HalWidgetFeed : null;
      return TaxEngine.buildTaxPlanFromSnapshot(snap, feed);
    }
    return null;
  }

  async function getIntegrationHealth() {
    if (hasDesktopApi() && window.pywebview.api.get_integration_health) {
      return window.pywebview.api.get_integration_health();
    }
    const resp = await fetch("http://127.0.0.1:8765/api/integration-health", { cache: "no-store" });
    if (!resp.ok) throw new Error("integration health unavailable");
    return resp.json();
  }

  async function getAutomationRegistry() {
    if (hasDesktopApi() && window.pywebview.api.get_automation_registry) {
      return window.pywebview.api.get_automation_registry();
    }
    const resp = await fetch("http://127.0.0.1:8765/api/automation-registry", { cache: "no-store" });
    if (!resp.ok) throw new Error("automation registry unavailable");
    return resp.json();
  }

  async function buildSupportBundle(note) {
    if (hasDesktopApi() && window.pywebview.api.build_support_bundle) {
      return window.pywebview.api.build_support_bundle(String(note || ""));
    }
    const resp = await fetch("http://127.0.0.1:8765/api/support-bundle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: String(note || "") }),
    });
    if (!resp.ok) throw new Error("support bundle unavailable");
    return resp.json();
  }

  async function getFinancialReports(syncExports) {
    if (hasDesktopApi() && window.pywebview.api.get_financial_reports) {
      return window.pywebview.api.get_financial_reports(Boolean(syncExports));
    }
    const q = syncExports ? "?syncExports=1" : "";
    const resp = await fetch(`http://127.0.0.1:8765/api/financial-reports${q}`, { cache: "no-store" });
    if (!resp.ok) throw new Error("financial reports unavailable");
    return resp.json();
  }

  async function getDailyCloseout() {
    if (hasDesktopApi() && window.pywebview.api.get_daily_closeout) {
      return window.pywebview.api.get_daily_closeout();
    }
    const resp = await fetch("http://127.0.0.1:8765/api/daily-closeout", { cache: "no-store" });
    if (!resp.ok) throw new Error("daily closeout unavailable");
    return resp.json();
  }

  async function runProgramSelfHeal(options) {
    const opts = options || {};
    if (hasDesktopApi() && window.pywebview.api.run_program_self_heal) {
      return window.pywebview.api.run_program_self_heal(
        Boolean(opts.fullPull),
        Boolean(opts.documentsOnly),
        String(opts.reason || "ui"),
      );
    }
    const resp = await fetch("http://127.0.0.1:8765/api/self-heal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        fullPull: Boolean(opts.fullPull),
        documentsOnly: Boolean(opts.documentsOnly),
        reason: opts.reason || "ui",
      }),
    });
    if (!resp.ok) throw new Error("program self-heal unavailable");
    return resp.json();
  }

  async function getProgramHelp(query) {
    if (hasDesktopApi() && window.pywebview.api.get_program_help) {
      return window.pywebview.api.get_program_help(String(query || ""));
    }
    return { text: "Program help requires the NR2 desktop app.", match: null };
  }

  async function searchHalMemories(query, limit) {
    if (hasDesktopApi() && window.pywebview.api.search_hal_memories) {
      return window.pywebview.api.search_hal_memories(String(query || ""), Number(limit || 5));
    }
    return { items: [], count: 0, text: "" };
  }

  async function grepProgramSource(query, limit) {
    if (hasDesktopApi() && window.pywebview.api.grep_program_source) {
      return window.pywebview.api.grep_program_source(String(query || ""), Number(limit || 24));
    }
    return { hits: [], count: 0, text: "Program source search requires the NR2 desktop app." };
  }

  async function readProgramFile(relPath, maxChars) {
    if (hasDesktopApi() && window.pywebview.api.read_program_file) {
      return window.pywebview.api.read_program_file(String(relPath || ""), Number(maxChars || 12000));
    }
    return { ok: false, text: "Program file read requires the NR2 desktop app." };
  }

  async function listProgramFiles(subdir, limit) {
    if (hasDesktopApi() && window.pywebview.api.list_program_files) {
      return window.pywebview.api.list_program_files(String(subdir || "site"), Number(limit || 80));
    }
    return { ok: false, files: [], text: "Program file list requires the NR2 desktop app." };
  }

  async function applyProgramPatch(relPath, oldString, newString, dryRun) {
    if (hasDesktopApi() && window.pywebview.api.apply_program_patch) {
      return window.pywebview.api.apply_program_patch(
        String(relPath || ""),
        String(oldString || ""),
        String(newString || ""),
        Boolean(dryRun),
      );
    }
    return { ok: false, text: "Program patch requires the NR2 desktop app." };
  }

  async function runHalValidation(timeoutSec) {
    if (hasDesktopApi() && window.pywebview.api.run_hal_validation) {
      return window.pywebview.api.run_hal_validation(Number(timeoutSec || 120));
    }
    return { ok: false, text: "HAL validation requires the NR2 desktop app.", exitCode: -1 };
  }

  async function runNodeSyntaxCheck(relPaths) {
    if (hasDesktopApi() && window.pywebview.api.run_node_syntax_check) {
      return window.pywebview.api.run_node_syntax_check(Array.isArray(relPaths) ? relPaths : []);
    }
    return { ok: false, text: "Syntax check requires the NR2 desktop app.", results: [] };
  }

  async function semanticSearchProgram(query, limit) {
    if (hasDesktopApi() && window.pywebview.api.semantic_search_program) {
      return window.pywebview.api.semantic_search_program(String(query || ""), Number(limit || 15));
    }
    return { hits: [], count: 0, text: "Semantic search requires the NR2 desktop app." };
  }

  async function runGitReadonly(command) {
    if (hasDesktopApi() && window.pywebview.api.run_git_readonly) {
      return window.pywebview.api.run_git_readonly(String(command || "status"));
    }
    return { ok: false, text: "Git read requires the NR2 desktop app." };
  }

  async function runAllowlistedCommand(commandId) {
    if (hasDesktopApi() && window.pywebview.api.run_allowlisted_command) {
      return window.pywebview.api.run_allowlisted_command(String(commandId || "validate-hal"));
    }
    return { ok: false, text: "Allowlisted commands require the NR2 desktop app." };
  }

  async function applyProgramPatches(patches, dryRun) {
    if (hasDesktopApi() && window.pywebview.api.apply_program_patches) {
      return window.pywebview.api.apply_program_patches(Array.isArray(patches) ? patches : [], Boolean(dryRun));
    }
    return { ok: false, text: "Batch patch requires the NR2 desktop app.", count: 0 };
  }

  return {
    hasDesktopApi,
    runtimeMode,
    desktopRequiredMessage,
    whenReady,
    readDataFile,
    storageGet,
    storageSet,
    getAppInfo,
    getImportBundle,
    getImportSyncStatus,
    refreshImports,
    syncAccountingDocuments,
    listPracticeSourceCatalog,
    fetchPracticeSource,
    pullPracticeSources,
    getChartOfAccounts,
    draftJournalEntry,
    listPostingQueue,
    enqueueJournalPosting,
    reviewPostingQueueEntry,
    bulkReviewPostingQueue,
    exportApprovedPostingQueue,
    webResearch,
    listHalMemories,
    rememberHalFact,
    rememberHalWebFindings,
    getTaxPlan,
    getIntegrationHealth,
    getAutomationRegistry,
    buildSupportBundle,
    getFinancialReports,
    getDailyCloseout,
    runProgramSelfHeal,
    getProgramHelp,
    grepProgramSource,
    readProgramFile,
    listProgramFiles,
    applyProgramPatch,
    runHalValidation,
    runNodeSyntaxCheck,
    semanticSearchProgram,
    runGitReadonly,
    runAllowlistedCommand,
    applyProgramPatches,
    searchHalMemories,
    readClipboard,
    writeClipboard,
    installClipboardHandlers,
    isTextField,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = DesktopBridge;
}
if (typeof window !== "undefined") {
  window.DesktopBridge = DesktopBridge;
}

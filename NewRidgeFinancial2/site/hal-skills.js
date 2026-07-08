/**
 * HAL Skills — client-side port of the legacy HAL backend business logic.
 *
 * Brings the legacy _legacy/app/hal/* Python capabilities into the single
 * frontend program with NO backend: accounting journal drafting + validation +
 * posting queue, claim packet readiness, office-manager attention + tasks,
 * knowledge memory, and PII sanitization.
 *
 * Everything here is local-only and read/draft-only. HAL only reads data from
 * SoftDent and QuickBooks; no external action or submission. The HAL firewall still runs
 * before any model call; these skills never perform external or destructive
 * operations.
 *
 * Browser + Node compatible (no DOM).
 */
const HalSkills = (function () {
  const PROGRAM_SCHEMA_VERSION = "nr2-hal-skill-v1";
  const SAFETY_DISCLAIMER =
    "HAL internal office manager (local only). External firewall locked. Draft only where applicable. Requires human review. " +
    "HAL may refresh imports, place validated data, and manage local tasks. No posting, writeback, email/fax/upload, or external delivery.";

  function skillMeta(kind, source) {
    return {
      schema: PROGRAM_SCHEMA_VERSION,
      kind,
      source: source || "hal-skills",
      localOnly: true,
      generatedAt: new Date().toISOString(),
    };
  }

  /* ============================================================
   * Sanitization — port of sanitization.py
   * ========================================================== */

  const NAME_AFTER_PATIENT_RE = /\b(patient\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b/gi;
  const SANITIZATION_RULES = [
    ["date", /\b\d{1,2}\/\d{1,2}\/\d{2,4}\b/g, "DATE_REDACTED"],
    ["phone", /\b(?:\+1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b/g, "PHONE_REDACTED"],
    ["mrn", /\bmrn\s*[:#-]?\s*[a-z0-9-]+\b/gi, "MRN_REDACTED"],
    ["account", /\b(?:account|acct|chart)\s*[:#-]?\s*[a-z0-9-]+\b/gi, "ACCOUNT_REDACTED"],
    ["email", /\b[\w.%-]+@[\w.-]+\.[A-Za-z]{2,}\b/g, "EMAIL_REDACTED"],
  ];

  function sanitizeText(text) {
    let sanitized = String(text == null ? "" : text).trim();
    const findings = [];
    sanitized = sanitized.replace(NAME_AFTER_PATIENT_RE, (match, prefix) => {
      findings.push({ label: "patient_name", replacement: "PATIENT_REDACTED" });
      return `${prefix}PATIENT_REDACTED`;
    });
    for (const [label, pattern, replacement] of SANITIZATION_RULES) {
      let matched = false;
      sanitized = sanitized.replace(pattern, () => {
        matched = true;
        return replacement;
      });
      if (matched) findings.push({ label, replacement });
    }
    return { sanitizedText: sanitized, findings };
  }

  const CHART_OF_ACCOUNTS = {
    1010: "Cash",
    1100: "Accounts Receivable",
    1310: "Prepaid Insurance",
    1500: "Equipment",
    2100: "Accounts Payable",
    2200: "Accrued Expenses",
    4000: "Patient Service Revenue",
    5050: "Insurance Expense",
    5200: "Dental Supplies Expense",
    6200: "Payroll Expense",
    6100: "Depreciation Expense",
    1590: "Accumulated Depreciation",
  };

  const TRANSACTION_TYPE_ALIASES = {
    prepaid: "prepaid_insurance",
    prepaid_insurance: "prepaid_insurance",
    depreciation: "depreciation",
    cash_receipt: "patient_cash_receipt",
    patient_cash_receipt: "patient_cash_receipt",
    equipment_purchase: "equipment_purchase",
    vendor_bill: "vendor_bill",
    payroll_accrual: "payroll_accrual",
    supplies_accrual: "supplies_accrual",
    patient_service_revenue: "patient_service_revenue",
  };

  const TRANSACTION_TYPE_RULES = [
    [["prepaid", "insurance"], "prepaid_insurance"],
    [["depreciation"], "depreciation"],
    [["payroll", "accrual"], "payroll_accrual"],
    [["supplies", "accrual"], "supplies_accrual"],
    [["supply", "accrual"], "supplies_accrual"],
    [["vendor", "bill"], "vendor_bill"],
    [["cash", "collection"], "patient_cash_receipt"],
    [["patient", "payment"], "patient_cash_receipt"],
    [["equipment", "purchase"], "equipment_purchase"],
  ];

  const TRANSACTION_TYPE_TEMPLATES = {
    prepaid_insurance: [
      { accountCode: "1310", accountName: "Prepaid Insurance", debit: "amount", credit: 0 },
      { accountCode: "1010", accountName: "Cash", debit: 0, credit: "amount" },
    ],
    depreciation: [
      { accountCode: "6100", accountName: "Depreciation Expense", debit: "amount", credit: 0 },
      { accountCode: "1590", accountName: "Accumulated Depreciation", debit: 0, credit: "amount" },
    ],
    patient_cash_receipt: [
      { accountCode: "1010", accountName: "Cash", debit: "amount", credit: 0 },
      { accountCode: "1100", accountName: "Accounts Receivable", debit: 0, credit: "amount" },
    ],
    equipment_purchase: [
      { accountCode: "1500", accountName: "Equipment", debit: "amount", credit: 0 },
      { accountCode: "1010", accountName: "Cash", debit: 0, credit: "amount" },
    ],
    vendor_bill: [
      { accountCode: "5200", accountName: "Dental Supplies Expense", debit: "amount", credit: 0 },
      { accountCode: "2100", accountName: "Accounts Payable", debit: 0, credit: "amount" },
    ],
    payroll_accrual: [
      { accountCode: "6200", accountName: "Payroll Expense", debit: "amount", credit: 0 },
      { accountCode: "2200", accountName: "Accrued Expenses", debit: 0, credit: "amount" },
    ],
    supplies_accrual: [
      { accountCode: "5200", accountName: "Dental Supplies Expense", debit: "amount", credit: 0 },
      { accountCode: "2200", accountName: "Accrued Expenses", debit: 0, credit: "amount" },
    ],
    patient_service_revenue: [
      { accountCode: "1100", accountName: "Accounts Receivable", debit: "amount", credit: 0 },
      { accountCode: "4000", accountName: "Patient Service Revenue", debit: 0, credit: "amount" },
    ],
  };

  const CLOSED_PERIODS = new Set(["2024-12", "2025-01"]);

  /** JS fallback COA for CI/browser-dev; desktop uses Python via resolveChartOfAccounts(). */
  let coaCache = null;

  function getChartOfAccounts() {
    return Object.assign({}, coaCache || CHART_OF_ACCOUNTS);
  }

  async function resolveChartOfAccounts() {
    if (coaCache) return coaCache;
    const bridge =
      typeof DesktopBridge !== "undefined"
        ? DesktopBridge
        : typeof globalThis !== "undefined" && globalThis.DesktopBridge
          ? globalThis.DesktopBridge
          : null;
    if (bridge && typeof bridge.hasDesktopApi === "function" && bridge.hasDesktopApi() && typeof bridge.getChartOfAccounts === "function") {
      try {
        const remote = await bridge.getChartOfAccounts();
        const accounts = remote && remote.accounts;
        if (accounts && typeof accounts === "object" && Object.keys(accounts).length) {
          coaCache = accounts;
          return coaCache;
        }
      } catch {
        /* fallback */
      }
    }
    coaCache = CHART_OF_ACCOUNTS;
    return coaCache;
  }

  function isPeriodOpen(period) {
    return !CLOSED_PERIODS.has(period);
  }

  function normalizeTransactionType(value) {
    if (typeof value !== "string") return null;
    const normalized = value.trim().toLowerCase().replace(/-/g, "_").replace(/ /g, "_");
    if (!normalized) return null;
    return TRANSACTION_TYPE_ALIASES[normalized] || null;
  }

  function inferTransactionType(description, context) {
    const explicit = normalizeTransactionType((context || {}).transaction_type);
    if (explicit) return explicit;
    const lower = String(description || "").toLowerCase();
    for (const [keywords, type] of TRANSACTION_TYPE_RULES) {
      if (keywords.every((k) => lower.includes(k))) return type;
    }
    return "patient_service_revenue";
  }

  function round2(value) {
    return Math.round((Number(value) + Number.EPSILON) * 100) / 100;
  }

  function draftJournalEntry(opts) {
    const { description, amount, context } = opts || {};
    const type = inferTransactionType(description, context || {});
    const template = TRANSACTION_TYPE_TEMPLATES[type];
    return template.map((line) => ({
      accountCode: line.accountCode,
      accountName: line.accountName,
      debit: round2(line.debit === "amount" ? amount : line.debit),
      credit: round2(line.credit === "amount" ? amount : line.credit),
      memo: description,
      transactionType: type,
    }));
  }

  function collectJournalAmounts(lines, field) {
    const values = [];
    const invalid = [];
    lines.forEach((line, index) => {
      let raw = line[field];
      if (raw === null || raw === undefined || raw === "") raw = 0;
      const num = Number(raw);
      if (Number.isNaN(num)) {
        values.push(0);
        invalid.push(`line ${index + 1} ${field}`);
      } else {
        values.push(num);
      }
    });
    return { values, invalid };
  }

  function buildJournalValidation(opts) {
    const { lines, chartOfAccounts, openPeriod } = opts || {};
    const coa = chartOfAccounts || getChartOfAccounts();
    const debit = collectJournalAmounts(lines, "debit");
    const credit = collectJournalAmounts(lines, "credit");
    const invalidAmountFields = debit.invalid.concat(credit.invalid);
    const debitTotal = round2(debit.values.reduce((a, b) => a + b, 0));
    const creditTotal = round2(credit.values.reduce((a, b) => a + b, 0));
    const balanced = debitTotal === creditTotal && invalidAmountFields.length === 0;
    const missingAccounts = lines
      .map((line) => String(line.accountCode || ""))
      .filter((code) => !Object.prototype.hasOwnProperty.call(coa, code));
    const hasNegative = debit.values.concat(credit.values).some((v) => v < 0);
    const issues = [];
    if (!balanced) issues.push("Journal entry is not balanced.");
    if (!openPeriod) issues.push("Accounting period is closed.");
    if (missingAccounts.length) issues.push(`Unknown account codes: ${missingAccounts.join(", ")}`);
    if (invalidAmountFields.length) issues.push(`Journal line amounts must be numeric: ${invalidAmountFields.join(", ")}`);
    if (hasNegative) issues.push("Journal line amounts must be non-negative.");
    return {
      balanced,
      debitTotal,
      creditTotal,
      openPeriod,
      accountValidationPassed: missingAccounts.length === 0,
      amountValidationPassed: !hasNegative && invalidAmountFields.length === 0,
      issues,
    };
  }

  function draftAndValidateJournal(opts) {
    const { description, period, amount, context } = opts || {};
    const lines = draftJournalEntry({ description, amount, context });
    const openPeriod = isPeriodOpen(period);
    const validation = buildJournalValidation({ lines, chartOfAccounts: getChartOfAccounts(), openPeriod });
    return {
      meta: skillMeta("accounting.journalDraft", "accounting"),
      description,
      period,
      amount,
      transactionType: lines[0] ? lines[0].transactionType : "patient_service_revenue",
      lines,
      validation,
      draftStatus: "draftOnly",
      postingStatus: "pendingReview",
      safety: { localOnly: true, notSubmitted: true, humanReviewRequired: true, postedToLedger: false },
      source: "javascript",
    };
  }

  async function draftAndValidateJournalAsync(opts) {
    const bridge =
      typeof DesktopBridge !== "undefined"
        ? DesktopBridge
        : typeof globalThis !== "undefined" && globalThis.DesktopBridge
          ? globalThis.DesktopBridge
          : null;
    if (bridge && typeof bridge.hasDesktopApi === "function" && bridge.hasDesktopApi() && typeof bridge.draftJournalEntry === "function") {
      try {
        await resolveChartOfAccounts();
        const remote = await bridge.draftJournalEntry({
          description: opts && opts.description,
          period: opts && opts.period,
          amount: opts && opts.amount,
          context: (opts && opts.context) || {},
        });
        if (remote && Array.isArray(remote.lines)) {
          return Object.assign({}, remote, {
            postingStatus: "pendingReview",
            safety: Object.assign(
              { localOnly: true, notSubmitted: true, humanReviewRequired: true, postedToLedger: false },
              remote.safety || {},
            ),
            source: "python",
          });
        }
      } catch {
        /* fallback to JS port for browser-dev / offline */
      }
    }
    await resolveChartOfAccounts();
    return draftAndValidateJournal(opts);
  }

  function formatJournalDraft(draft) {
    const lines = [
      `Journal draft (local · draft only · not posted) — ${draft.transactionType.replace(/_/g, " ")}:`,
      `Period ${draft.period} · ${draft.validation.openPeriod ? "OPEN" : "CLOSED"}`,
    ];
    draft.lines.forEach((l) => {
      const dr = l.debit ? `Dr ${l.debit.toFixed(2)}` : "";
      const cr = l.credit ? `Cr ${l.credit.toFixed(2)}` : "";
      lines.push(`  ${l.accountCode} ${l.accountName}: ${dr}${cr}`);
    });
    lines.push(`Balanced: ${draft.validation.balanced ? "yes" : "no"} (Dr ${draft.validation.debitTotal} / Cr ${draft.validation.creditTotal})`);
    if (draft.validation.issues.length) lines.push("Issues: " + draft.validation.issues.join("; "));
    lines.push("Stays in the local review queue only. HAL reads QuickBooks only.");
    return lines.join("\n");
  }

  /* ============================================================
   * Claim packet readiness — port of claim_packet_readiness.py
   * (adapted to the local claims sample/persisted data)
   * ========================================================== */

  const OPEN_CLAIM_STATUSES = new Set(["denied", "needs review", "needs-review", "draft", "submitted", "pending", "open"]);

  function assessClaimReadiness(claim) {
    const status = String(claim.status || "").toLowerCase();
    const hasClaimId = !!claim.id;
    const hasProcedure = !!claim.procedure && claim.procedure !== "—";
    const hasAmount = !!claim.amount && claim.amount !== "$0.00";
    const hasNarrative = !!claim.narrative || !!claim.clinicalNote;
    const isDenied = status.includes("denied");

    const missing = [];
    if (!hasProcedure) missing.push("Procedure facts missing");
    if (!hasAmount) missing.push("Billed amount missing");
    if (!hasNarrative && (isDenied || status.includes("review"))) missing.push("Clinical note / narrative missing");

    let readiness;
    if (!hasClaimId) {
      readiness = "blocked";
    } else if (hasProcedure && hasAmount && (hasNarrative || !isDenied)) {
      readiness = hasNarrative ? "ready" : "needs_review";
    } else if (hasProcedure || hasAmount) {
      readiness = "needs_review";
    } else {
      readiness = "blocked";
    }

    if (readiness === "ready" || readiness === "needs_review") {
      missing.push("Human review required");
    }

    const priority = readiness === "blocked" ? "high" : isDenied ? "high" : readiness === "needs_review" ? "normal" : "low";
    const canPrepareDraft = hasClaimId && readiness !== "blocked";

    const actions = [];
    if (missing.includes("Clinical note / narrative missing")) actions.push("Locate or draft the clinical narrative for staff review.");
    if (!hasAmount) actions.push("Confirm the billed amount before assessing readiness.");
    if (canPrepareDraft) actions.push("Prepare a local draft for human review.");
    actions.push("Nothing has been submitted or sent.");

    let summary;
    if (readiness === "ready") summary = "Packet appears ready for human review. Nothing has been submitted or sent.";
    else if (readiness === "needs_review") summary = canPrepareDraft ? "Local draft can be prepared. Staff must review before use." : "Needs review before use.";
    else summary = missing.length ? `Blocked: ${missing[0]}.` : "Blocked until required local facts are available.";

    return {
      packetId: `cpr-${claim.id || "unknown"}`,
      claimRef: claim.id || null,
      patientLabel: claim.patient || null,
      status: readiness,
      priority,
      blockers: readiness === "blocked" ? missing.slice() : [],
      missingItems: missing,
      recommendedNextActions: Array.from(new Set(actions)),
      canPrepareLocalDraft: canPrepareDraft,
      localDraftStatus: canPrepareDraft ? "draftAvailable" : "needsFacts",
      staffSummary: summary,
      safety: { localOnly: true, notSubmitted: true, humanReviewRequired: true, externalDeliveryAllowed: false },
    };
  }

  function buildClaimReadinessResponse(claimsList) {
    const items = (claimsList || []).map(assessClaimReadiness);
    return {
      meta: skillMeta("claims.readiness", "claims"),
      summary: {
        readyCount: items.filter((i) => i.status === "ready").length,
        needsReviewCount: items.filter((i) => i.status === "needs_review").length,
        blockedCount: items.filter((i) => i.status === "blocked").length,
        totalCount: items.length,
      },
      items,
      safetyDisclaimer: SAFETY_DISCLAIMER,
      localOnly: true,
      submissionStatus: "notSubmitted",
    };
  }

  function formatClaimReadinessAnswer(resp) {
    const s = resp.summary;
    const lines = [
      "Claim packet readiness (local only):",
      `- Ready: ${s.readyCount}`,
      `- Needs review: ${s.needsReviewCount}`,
      `- Blocked: ${s.blockedCount}`,
      "",
      "HAL can prepare a local packet and draft. Staff must review before use. Nothing has been submitted or sent.",
    ];
    const examples = resp.items.slice(0, 4);
    if (examples.length) {
      lines.push("", "Examples:");
      examples.forEach((item) => {
        const headline = item.claimRef ? `${item.claimRef}: ${item.staffSummary}` : item.staffSummary;
        lines.push(`- ${headline}`);
      });
    }
    return lines.join("\n");
  }

  /* ============================================================
   * Office-manager attention — port of office_manager_attention.py
   * (adapted to the local program snapshot)
   * ========================================================== */

  function buildOfficeManagerAttention(snapshot, taskMetrics) {
    const items = [];
    const missingCodes = new Set();
    const snap = snapshot || {};

    const claims = snap.claims;
    if (claims) {
      const denied = (claims.byStatus && (claims.byStatus.Denied || claims.byStatus.denied)) || 0;
      const review = (claims.byStatus && (claims.byStatus["Needs Review"] || claims.byStatus.needsReview)) || 0;
      if (denied > 0) {
        items.push({
          itemId: "claims-denied",
          category: "claims_follow_up",
          severity: denied >= 3 ? "warning" : "info",
          title: "Denied claims need follow-up",
          detail: `${denied} denied claim(s) are visible in the local claims workbench.`,
          actionHint: "Use Claims Workbench to prepare a local review draft. No payer contact.",
          count: denied,
        });
      }
      if (review > 0) {
        items.push({
          itemId: "claims-needs-review",
          category: "claims_follow_up",
          severity: review >= 5 ? "warning" : "info",
          title: "Claims in the Needs Review lane",
          detail: `${review} claim(s) await staff review before any payer-facing step.`,
          actionHint: "Work the Needs Review lane first. Nothing is submitted.",
          count: review,
        });
      }
    } else {
      missingCodes.add("missing_softdent_claims_export");
    }

    const documents = snap.documents;
    if (documents && documents.posting) {
      const pending = (documents.posting.find((p) => /pending/i.test(p.label)) || {}).count || 0;
      if (pending > 0) {
        items.push({
          itemId: "posting-queue-pending",
          category: "revenue",
          severity: "info",
          title: "Accounting posting queue needs review",
          detail: `${pending} local posting-queue item(s) remain pending human review.`,
          actionHint: "Review the accounting posting queue before month-end close.",
          count: pending,
        });
      }
    }

    const qb = snap.dashboards && snap.dashboards.quickbooks;
    if (qb && /blocked|stale|pending/i.test(String(qb.syncStatus || qb.lastSync || ""))) {
      // QuickBooks registry state is Blocked in the program; surface as revenue attention.
      items.push({
        itemId: "quickbooks-source-health",
        category: "revenue",
        severity: "warning",
        title: "QuickBooks source needs attention",
        detail: "QuickBooks sync is not current; expense and revenue totals may be stale.",
        actionHint: "Review revenue inputs before month-end office-manager summaries.",
      });
    }

    if (taskMetrics) {
      const openTasks =
        (taskMetrics.openCount || 0) + (taskMetrics.inProgressCount || 0) + (taskMetrics.blockedCount || 0);
      if (openTasks > 0) {
        items.push({
          itemId: "local-office-tasks-open",
          category: "local_tasks",
          severity: (taskMetrics.urgentOpenCount || 0) > 0 ? "warning" : "info",
          title: "Unresolved local office tasks",
          detail: `${openTasks} local office task(s) remain open, in progress, or blocked.`,
          actionHint: "Work local tasks inside this app only. HAL reads SoftDent and QuickBooks only; no posting, writes, or external delivery.",
          count: openTasks,
        });
      }
    }

    const practice = snap.dashboards && snap.dashboards.practice;
    const hasTp = practice && practice.configured && practice.configured.treatmentPlans;
    const hasHr = practice && practice.configured && practice.configured.hygieneRecall;
    [
      ["treatment-plan-unavailable", "treatment_plan", "Treatment plan follow-up is limited", "No approved treatment-plan export source is available yet.", "missing_treatment_plan_export", () => !hasTp],
      ["hygiene-recall-unavailable", "hygiene_recall", "Hygiene and recall follow-up is limited", "No approved recall or hygiene export source is available yet.", "missing_hygiene_recall_export", () => !hasHr],
      ["vendor-tracker-local-only", "vendor", "Vendor and software issues are local-only", "Vendor/software issue tracking uses local records in this app only.", "missing_vendor_tracker_source", () => true],
    ].forEach(([id, category, title, detail, code, include]) => {
      if (typeof include === "function" && !include()) return;
      missingCodes.add(code);
      items.push({ itemId: id, category, severity: "info", title, detail, actionHint: "Use local office tasks until a real export source is approved.", missingDataCodes: [code] });
    });

    return {
      meta: skillMeta("office.attention", "officeManager"),
      summary: `${items.length} office-manager attention item(s) are visible. All actions remain local only and not submitted. HAL reads SoftDent and QuickBooks only.`,
      safetyDisclaimer: SAFETY_DISCLAIMER,
      items,
      missingDataCodes: Array.from(missingCodes).sort(),
      localOnly: true,
      submissionStatus: "notSubmitted",
    };
  }

  function formatOfficeManagerAttention(resp) {
    const lines = ["Office-manager attention (local only):", resp.summary, ""];
    resp.items.slice(0, 8).forEach((item) => {
      const sev = item.severity === "critical" ? "[!]" : item.severity === "warning" ? "[*]" : "[i]";
      lines.push(`${sev} ${item.title}${item.count ? ` (${item.count})` : ""} — ${item.detail}`);
    });
    lines.push("", resp.safetyDisclaimer);
    return lines.join("\n");
  }

  /* ============================================================
   * HAL sidenotes — local staff scratch notes monitored by HAL
   * (pure helpers; persistence handled by the app via DesktopBridge)
   * ========================================================== */

  const VALID_SIDENOTE_STATUSES = new Set(["open", "pinned", "archived"]);
  const VALID_SIDENOTE_PRIORITIES = new Set(["low", "normal", "high"]);

  function sideNoteFingerprint(notes) {
    return (notes || [])
      .map((n) => `${n.noteId}:${n.updatedAt || ""}:${n.status || ""}`)
      .sort()
      .join("|");
  }

  function createSideNote(req, opts) {
    const now = new Date().toISOString();
    const actor = (opts && opts.actor) || "local-user";
    const text = sanitizeText(String((req && req.text) || "").trim());
    if (text.length < 2) throw new Error("Sidenote text must be at least 2 characters.");
    const status = VALID_SIDENOTE_STATUSES.has(req.status) ? req.status : "open";
    const priority = VALID_SIDENOTE_PRIORITIES.has(req.priority) ? req.priority : "normal";
    const tags = Array.isArray(req.tags) ? req.tags.map((t) => String(t).trim()).filter(Boolean).slice(0, 8) : [];
    return {
      meta: skillMeta("hal.sidenote", "hal"),
      noteId: uid("sn"),
      text,
      status,
      priority,
      tags,
      createdBy: actor,
      createdAt: now,
      updatedAt: now,
      localOnly: true,
      externalActionPerformed: false,
      softdentWritebackPerformed: false,
    };
  }

  function applySideNoteUpdate(existing, updates) {
    if (!existing) throw new Error("Sidenote not found.");
    const next = Object.assign({}, existing);
    if (updates.text != null) {
      const t = sanitizeText(String(updates.text).trim());
      if (t.length < 2) throw new Error("Sidenote text must be at least 2 characters.");
      next.text = t;
    }
    if (updates.status != null) {
      if (!VALID_SIDENOTE_STATUSES.has(updates.status)) throw new Error(`Unsupported sidenote status: ${updates.status}`);
      next.status = updates.status;
    }
    if (updates.priority != null) {
      if (!VALID_SIDENOTE_PRIORITIES.has(updates.priority)) throw new Error(`Unsupported sidenote priority: ${updates.priority}`);
      next.priority = updates.priority;
    }
    if (updates.tags != null) next.tags = updates.tags.slice();
    next.updatedAt = new Date().toISOString();
    return next;
  }

  function buildSideNoteMonitor(notes, prevMonitor) {
    const list = notes || [];
    const active = list.filter((n) => n.status !== "archived");
    const fingerprint = sideNoteFingerprint(list);
    const prevFp = prevMonitor && prevMonitor.fingerprint;
    const recentThresholdMs = 24 * 60 * 60 * 1000;
    const recent = active
      .filter((n) => Date.now() - Date.parse(n.updatedAt || n.createdAt || 0) < recentThresholdMs)
      .sort((a, b) => Date.parse(b.updatedAt || 0) - Date.parse(a.updatedAt || 0))
      .slice(0, 6);
    return {
      meta: skillMeta("hal.sidenoteMonitor", "hal"),
      checkedAt: new Date().toISOString(),
      fingerprint,
      hasChanges: !!(prevFp && prevFp !== fingerprint),
      totalCount: list.length,
      activeCount: active.length,
      openCount: active.filter((n) => n.status === "open").length,
      pinnedCount: active.filter((n) => n.status === "pinned").length,
      highPriorityCount: active.filter((n) => n.priority === "high").length,
      archivedCount: list.length - active.length,
      recent,
      localOnly: true,
      externalActionPerformed: false,
      softdentWritebackPerformed: false,
    };
  }

  function formatSideNoteMonitor(monitor, notes) {
    const m = monitor || buildSideNoteMonitor(notes || []);
    const lines = [
      "HAL sidenotes monitor (local only · not submitted · HAL watches persisted storage):",
      `Checked ${m.checkedAt || "—"} · ${m.activeCount} active · ${m.openCount} open · ${m.pinnedCount} pinned · ${m.highPriorityCount} high priority`,
    ];
    if (m.hasChanges) lines.push("", "Changes detected since the last monitor check.");
    const active = (notes || []).filter((n) => n.status !== "archived");
    if (!active.length) {
      lines.push("", 'No active sidenotes. Add one below or say "Add sidenote: recall patient about claim".');
    } else {
      lines.push("", "Active notes:");
      active.slice(0, 12).forEach((n) => {
        const tagStr = n.tags && n.tags.length ? ` [${n.tags.join(", ")}]` : "";
        lines.push(`- [${n.status}/${n.priority}] ${String(n.text || "").slice(0, 160)}${tagStr}`);
      });
    }
    lines.push("", SAFETY_DISCLAIMER);
    return lines.join("\n");
  }

  function formatSideNotesList(notes) {
    const active = (notes || []).filter((n) => n.status !== "archived");
    const lines = [
      `Local sidenotes (${active.length} active · local only):`,
    ];
    if (!active.length) {
      lines.push("", 'No sidenotes yet. Say "Add sidenote: follow up on hygiene recall" to add one.');
    } else {
      lines.push("");
      active.slice(0, 15).forEach((n) => {
        lines.push(`- [${n.status}] (${n.priority}) ${String(n.text || "")}`);
      });
    }
    return lines.join("\n");
  }

  /* ============================================================
   * Office-manager tasks — port of office_manager_task_service.py
   * (pure helpers; persistence handled by the app via DesktopBridge)
   * ========================================================== */

  const VALID_TASK_STATUSES = new Set(["open", "in_progress", "blocked", "completed", "dismissed"]);
  const VALID_TASK_PRIORITIES = new Set(["low", "normal", "high", "urgent"]);
  const VALID_TASK_CATEGORIES = new Set([
    "claim",
    "patient_prep",
    "documentation",
    "treatment_plan",
    "hygiene_recall",
    "compliance",
    "vendor",
    "report",
    "other",
  ]);

  function uid(prefix) {
    return `${prefix || "omt"}-${Date.now().toString(36)}${Math.floor(Math.random() * 1e6).toString(36)}`;
  }

  function createTask(req, opts) {
    const now = new Date().toISOString();
    const actor = (opts && opts.actor) || "local-user";
    const title = String((req && req.title) || "").trim();
    if (title.length < 3) throw new Error("Task title must be at least 3 characters.");
    const category = VALID_TASK_CATEGORIES.has(req.category) ? req.category : "other";
    const priority = VALID_TASK_PRIORITIES.has(req.priority) ? req.priority : "normal";
    return {
      meta: skillMeta("office.task", "officeManager"),
      taskId: req.taskId || uid("omt"),
      title,
      description: String((req && req.description) || req.notes || "").trim(),
      category,
      status: VALID_TASK_STATUSES.has(req.status) ? req.status : "open",
      priority,
      patientLabel: req.patientLabel || req.patient_label || null,
      claimId: req.claimId || req.claim_id || null,
      sourceRefs: (req.sourceRefs || req.source_refs || []).slice(),
      missingDataCodes: (req.missingDataCodes || req.missing_data_codes || []).slice(),
      dueDate: req.dueDate || req.due_date || null,
      assignedTo: req.assignedTo || req.assigned_to || null,
      source: req.source || null,
      sourceId: req.sourceId || req.source_id || null,
      surface: req.surface || null,
      dueHint: req.dueHint || req.due_hint || null,
      blockingReason: req.blockingReason || req.blocking_reason || null,
      halGenerated: req.halGenerated === true || (opts && opts.actor === "hal-proactive") || (opts && opts.actor === "hal-office-manager"),
      lastObservedAt: req.lastObservedAt || req.last_observed_at || now,
      resolvedWhen: req.resolvedWhen || req.resolved_when || null,
      notes: String((req && req.notes) || "").trim() || null,
      createdBy: actor,
      createdAt: req.createdAt || now,
      updatedAt: now,
      localOnly: true,
      externalActionPerformed: false,
      softdentWritebackPerformed: false,
    };
  }

  function findTaskBySourceId(tasks, sourceId) {
    const key = String(sourceId || "").trim();
    if (!key) return null;
    return (tasks || []).find((task) => String(task.sourceId || "") === key) || null;
  }

  function upsertHalTask(tasks, req, opts) {
    const list = Array.isArray(tasks) ? tasks.slice() : [];
    const sourceId = req && (req.sourceId || req.source_id);
    const existing = sourceId ? findTaskBySourceId(list, sourceId) : null;
    const now = new Date().toISOString();
    if (existing) {
      const next = applyTaskUpdate(existing, {
        title: req.title,
        description: req.description || req.notes,
        priority: req.priority,
        status: existing.status === "completed" || existing.status === "dismissed" ? "open" : existing.status,
        sourceRefs: req.sourceRefs,
        missingDataCodes: req.missingDataCodes,
      });
      next.source = req.source || next.source;
      next.surface = req.surface || next.surface;
      next.dueHint = req.dueHint || next.dueHint;
      next.blockingReason = req.blockingReason || next.blockingReason;
      next.halGenerated = true;
      next.lastObservedAt = now;
      next.notes = req.notes || next.notes;
      const index = list.findIndex((task) => task.taskId === existing.taskId);
      if (index >= 0) list[index] = next;
      return { task: next, created: false, tasks: list };
    }
    const created = createTask(req, opts);
    list.unshift(created);
    return { task: created, created: true, tasks: list };
  }

  function autoResolveHalTasks(tasks, activeSourceIds) {
    const active = new Set((activeSourceIds || []).map((id) => String(id)));
    const now = new Date().toISOString();
    return (tasks || []).map((task) => {
      if (!task.halGenerated || !task.sourceId) return task;
      if (task.status !== "open" && task.status !== "blocked") return task;
      if (active.has(String(task.sourceId))) return task;
      return applyTaskUpdate(task, { status: "completed", resolvedWhen: now });
    });
  }

  function applyTaskUpdate(existing, updates) {
    if (!existing) throw new Error("Task not found.");
    const next = Object.assign({}, existing);
    if (updates.title != null) {
      const t = String(updates.title).trim();
      if (t.length < 3) throw new Error("Task title must be at least 3 characters.");
      next.title = t;
    }
    if (updates.description != null) next.description = String(updates.description).trim();
    if (updates.category != null) {
      if (!VALID_TASK_CATEGORIES.has(updates.category)) throw new Error(`Unsupported task category: ${updates.category}`);
      next.category = updates.category;
    }
    if (updates.status != null) {
      if (!VALID_TASK_STATUSES.has(updates.status)) throw new Error(`Unsupported task status: ${updates.status}`);
      next.status = updates.status;
    }
    if (updates.priority != null) {
      if (!VALID_TASK_PRIORITIES.has(updates.priority)) throw new Error(`Unsupported task priority: ${updates.priority}`);
      next.priority = updates.priority;
    }
    ["patientLabel", "claimId", "dueDate", "assignedTo"].forEach((field) => {
      if (updates[field] != null) next[field] = updates[field];
    });
    if (updates.sourceRefs != null) next.sourceRefs = updates.sourceRefs.slice();
    if (updates.missingDataCodes != null) next.missingDataCodes = updates.missingDataCodes.slice();
    if (updates.source != null) next.source = updates.source;
    if (updates.sourceId != null) next.sourceId = updates.sourceId;
    if (updates.surface != null) next.surface = updates.surface;
    if (updates.dueHint != null) next.dueHint = updates.dueHint;
    if (updates.blockingReason != null) next.blockingReason = updates.blockingReason;
    if (updates.lastObservedAt != null) next.lastObservedAt = updates.lastObservedAt;
    if (updates.resolvedWhen != null) next.resolvedWhen = updates.resolvedWhen;
    if (updates.notes != null) next.notes = updates.notes;
    if (updates.status === "completed" || updates.status === "dismissed") {
      next.resolvedWhen = updates.resolvedWhen || new Date().toISOString();
    }
    next.updatedAt = new Date().toISOString();
    return next;
  }

  function computeTaskMetrics(tasks) {
    const list = tasks || [];
    const count = (status) => list.filter((t) => t.status === status).length;
    return {
      meta: skillMeta("office.taskMetrics", "officeManager"),
      openCount: count("open"),
      inProgressCount: count("in_progress"),
      blockedCount: count("blocked"),
      completedCount: count("completed"),
      dismissedCount: count("dismissed"),
      urgentOpenCount: list.filter((t) => t.status === "open" && t.priority === "urgent").length,
      localOnly: true,
      externalActionPerformed: false,
      softdentWritebackPerformed: false,
    };
  }

  /* ============================================================
   * Knowledge memory — port of knowledge_memory.py
   * ========================================================== */

  const APPROVED_STATUS = "approved";
  const INDEXABLE_CONFIDENCE = new Set(["high", "medium"]);
  const BLOCKED_SENSITIVITY = new Set(["restricted", "prohibited"]);
  const FORBIDDEN_TEXT_PATTERNS = [
    "patientname,mrn,claimid",
    "api_key",
    "password=",
    "secret=",
    "bearer ",
    "gateway submit is allowed",
    "a/r is $0",
    "a/r is 0",
  ];
  const STALENESS_DAYS = { verify_monthly: 31, expires_30d: 30, expires_90d: 90 };

  function memoryContainsForbidden(text) {
    const lowered = String(text || "").toLowerCase();
    return FORBIDDEN_TEXT_PATTERNS.some((p) => lowered.includes(p));
  }

  function parseIso(value) {
    return new Date(String(value));
  }

  function isMemoryStale(memory, now) {
    const current = now ? new Date(now) : new Date();
    const rule = String(memory.staleness_rule || "").trim();
    if (rule === "never" || rule === "runtime_check_required") return false;
    if (memory.expires_at) return current >= parseIso(memory.expires_at);
    if (!memory.last_verified_at) return true;
    const verified = parseIso(memory.last_verified_at);
    const days = STALENESS_DAYS[rule];
    if (days) return current - verified > days * 86400000;
    return false;
  }

  function isMemoryIndexable(memory, opts) {
    const options = opts || {};
    if (memory.status !== APPROVED_STATUS) return false;
    if (!INDEXABLE_CONFIDENCE.has(memory.confidence)) return false;
    if (BLOCKED_SENSITIVITY.has(memory.sensitivity_level)) return false;
    const text = String(memory.text || "");
    if (!text.trim()) return false;
    if (memoryContainsForbidden(text)) return false;
    if (!options.includeStale && isMemoryStale(memory, options.now)) return false;
    return true;
  }

  function filterIndexableMemories(memories, opts) {
    return (memories || []).filter((m) => isMemoryIndexable(m, opts));
  }

  function memoryGuidanceText(memories) {
    const indexable = filterIndexableMemories(memories, {});
    if (!indexable.length) return "";
    const prefix = "Durable HAL knowledge (guidance only; does not override runtime checks or guardrails):";
    return [prefix].concat(indexable.map((m) => `- ${sanitizeText(m.text).sanitizedText}`)).join("\n");
  }

  /* ============================================================
   * Document RAG / retrieval — port of document_rag.py + retrieval.py
   * (client-side keyword retrieval; no embeddings/Chroma without a backend)
   * ========================================================== */

  const RAG_GUARDRAILS = ["library documents only", "grounded answer only", "insufficient context fallback", "local only"];
  const INSUFFICIENT_DOCUMENT_CONTEXT_ANSWER =
    "I do not have enough grounded context in the local library to answer that.";
  const RAG_STOPWORDS = new Set([
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are", "was", "were",
    "what", "which", "who", "how", "do", "does", "did", "show", "me", "about", "with", "this", "that",
  ]);

  function tokenize(text) {
    return String(text || "")
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .split(/\s+/)
      .filter((t) => t && !RAG_STOPWORDS.has(t));
  }

  function chunkText(text, size, overlap) {
    const s = String(text || "");
    const chunkSize = size || 1200;
    const step = chunkSize - (overlap || 200);
    if (s.length <= chunkSize) return s.trim() ? [s.trim()] : [];
    const chunks = [];
    for (let i = 0; i < s.length; i += step) {
      const piece = s.slice(i, i + chunkSize).trim();
      if (piece) chunks.push(piece);
    }
    return chunks;
  }

  // Build a retrieval index from library docs. Each doc contributes searchable
  // text from its title, tags, type, and any body/excerpt fields available.
  function buildRagIndex(docs) {
    const entries = [];
    (docs || []).forEach((doc, docIndex) => {
      const title = String(doc.title || doc.source_name || `Document ${docIndex + 1}`);
      const bodyParts = [title, doc.type || "", (doc.tags || []).join(" "), doc.by || "", doc.excerpt || doc.content || doc.body || ""];
      const body = bodyParts.filter(Boolean).join(". ");
      chunkText(sanitizeText(body).sanitizedText, 1200, 200).forEach((chunk, chunkIndex) => {
        entries.push({
          sourceId: `${title}:chunk:${chunkIndex + 1}`,
          title,
          category: "library_document",
          content: chunk,
          tokens: tokenize(chunk),
        });
      });
    });
    return entries;
  }

  function queryRag(index, question, topK) {
    const limit = topK || 4;
    const qTokens = tokenize(question);
    if (!qTokens.length || !index || !index.length) return [];
    const qSet = new Set(qTokens);
    const scored = index
      .map((entry) => {
        let overlap = 0;
        const seen = new Set();
        entry.tokens.forEach((t) => {
          if (qSet.has(t) && !seen.has(t)) {
            seen.add(t);
            overlap += 1;
          }
        });
        const score = overlap / qSet.size;
        return { entry, score };
      })
      .filter((s) => s.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit);
    return scored.map(({ entry, score }) => ({
      sourceId: entry.sourceId,
      title: entry.title,
      category: entry.category,
      content: entry.content,
      excerpt: `${entry.title}: ${entry.content}`,
      score: Math.round(score * 100) / 100,
    }));
  }

  function buildDocumentAnswerPrompt(question, retrievedContext) {
    const blocks = (retrievedContext || []).map((item, i) => `[${i + 1}] File: ${item.title}\nContext: ${item.excerpt}`);
    return (
      "You answer questions only from the local library context below. " +
      "If the context does not support the answer, respond exactly with: " +
      INSUFFICIENT_DOCUMENT_CONTEXT_ANSWER +
      " Do not invent figures, dates, or file citations. Mention source file names when relevant.\n\n" +
      `Question:\n${question}\n\n` +
      `Library context:\n${blocks.join("\n\n")}\n`
    );
  }

  function answerFromLibrary(question, docs, topK) {
    const index = buildRagIndex(docs);
    const context = queryRag(index, question, topK);
    const grounded = context.some((c) => String(c.content || "").trim());
    return {
      meta: skillMeta("library.ask", "library"),
      mode: "client-keyword-rag-v1",
      question,
      retrievedContext: context,
      guardrails: RAG_GUARDRAILS,
      grounded,
      answer: grounded ? null : INSUFFICIENT_DOCUMENT_CONTEXT_ANSWER,
      prompt: grounded ? buildDocumentAnswerPrompt(question, context) : null,
      localOnly: true,
    };
  }

  function formatRagResult(result) {
    if (!result.grounded) {
      return INSUFFICIENT_DOCUMENT_CONTEXT_ANSWER + "\n\nLibrary search is local-only and grounded; nothing was sent externally.";
    }
    const lines = [`Found ${result.retrievedContext.length} grounded match(es) in the local library:`, ""];
    result.retrievedContext.forEach((c) => lines.push(`- ${c.title} (match ${c.score}) — ${c.content.slice(0, 160)}`));
    lines.push("", "Library search results (local snippets only — not a synthesized answer):");
    return lines.join("\n");
  }

  /* ============================================================
   * SoftDent read source status + missing-data codes
   * — port of softdent_read_models.py honesty rules
   * ========================================================== */

  const SOFTDENT_MISSING_DATA_CODES = {
    claims: "missing_softdent_claims_export",
    clinicalNotes: "missing_softdent_clinical_notes_export",
    ar: "missing_softdent_ar",
    ledger: "missing_softdent_patient_ledger_export",
    procedures: "missing_softdent_procedures_export",
    eodReport: "missing_softdent_eod_report",
  };

  // Determine which SoftDent fact lanes are available from the snapshot, never
  // fabricating a $0 A/R balance when no verified A/R source exists.
  function softDentReadSourceStatus(snapshot) {
    const snap = snapshot || {};
    const bundle = snap.importBundle || {};
    const clinicalRows = (bundle.softdent && bundle.softdent.clinicalNotes && bundle.softdent.clinicalNotes.rows) || [];
    const claimsAvailable = !!(snap.claims && snap.claims.total > 0);
    const ar = snap.dashboards && snap.dashboards.ar;
    const arRows = (bundle.softdent && bundle.softdent.ar && bundle.softdent.ar.rows) || [];
    const arAvailable = !!(
      ar &&
      ((Array.isArray(ar.buckets) && ar.buckets.length) ||
        (Array.isArray(ar.aging) && ar.aging.length) ||
        ar.total)
    ) || arRows.length > 0;
    const missing = [];
    if (!claimsAvailable) missing.push(SOFTDENT_MISSING_DATA_CODES.claims);
    if (!clinicalRows.length) missing.push(SOFTDENT_MISSING_DATA_CODES.clinicalNotes);
    if (!arAvailable) missing.push(SOFTDENT_MISSING_DATA_CODES.ar);
    return {
      meta: skillMeta("softdent.readStatus", "softdent"),
      claimsAvailable,
      clinicalNotesAvailable: clinicalRows.length > 0,
      arAvailable,
      missingDataCodes: missing,
      note: "A/R is only reported from a verified source; HAL never fabricates a $0 balance.",
    };
  }

  const SOURCE_SYSTEM_PROFILES = {
    softdent: {
      label: "SoftDent",
      role: "Practice management system of record",
      owns: [
        "Daily production and collections",
        "Insurance claims pipeline and claim status",
        "Verified dental A/R aging buckets",
        "Patient vs insurance responsibility splits",
        "Clinical notes, treatment plans, and case acceptance (when exported)",
      ],
      doesNotOwn: [
        "General-ledger revenue or net income",
        "Operating expense categories or payroll GL totals",
        "QuickBooks journal entries or posting",
      ],
      importDir: "app_data/nr2/document_inbox/softdent",
      pages: ["softdent", "ar", "claims", "practice"],
      documentTypes: ["Claim", "A/R Aging", "Production Summary"],
    },
    quickbooks: {
      label: "QuickBooks",
      role: "Accounting system of record",
      owns: [
        "Monthly revenue and P&L",
        "Operating expenses and expense categories",
        "Net income and accounting-period financial totals",
        "Vendor-bill style expense pivots for review",
      ],
      doesNotOwn: [
        "Chairside production or collections",
        "Claim lifecycle or payer submission status",
        "Dental A/R aging buckets or per-patient balances",
      ],
      importDir: "app_data/nr2/document_inbox/quickbooks",
      pages: ["quickbooks", "financial"],
      documentTypes: ["Bill", "Statement"],
    },
  };

  function documentQueueSourceKey(doc) {
    const system = String((doc && doc.sourceSystem) || "").trim().toLowerCase();
    if (system === "quickbooks" || system === "softdent") return system;
    if (doc && doc.autoImported) return "ocr";
    return "manual";
  }

  function formatSourceSystemGuide(snapshot) {
    const snap = snapshot || {};
    const bundle = snap.importBundle || {};
    const sd = snap.dashboards && snap.dashboards.softdent;
    const qb = snap.dashboards && snap.dashboards.quickbooks;
    const docs = snap.documents || {};
    const lines = [
      "SoftDent vs QuickBooks — source boundary guide (read-only):",
      "",
      "These are two different systems. HAL keeps them separate and never treats their totals as interchangeable.",
      "",
    ];

    Object.entries(SOURCE_SYSTEM_PROFILES).forEach(([key, profile]) => {
      lines.push(`${profile.label} (${profile.role})`);
      lines.push(`  Import cache: ${profile.importDir}`);
      lines.push(`  Program pages: ${profile.pages.join(", ")}`);
      lines.push("  HAL uses this source for:");
      profile.owns.forEach((item) => lines.push(`    - ${item}`));
      lines.push("  Do NOT use this source for:");
      profile.doesNotOwn.forEach((item) => lines.push(`    - ${item}`));
      lines.push("");
    });

    lines.push("Reconciliation rules (review signals only — not proof they must match):");
    lines.push("- SoftDent production/collections vs QuickBooks revenue: compare periods before flagging drift.");
    lines.push("- SoftDent verified A/R aging vs claims balances: dental receivables only — never QuickBooks A/R.");
    lines.push("- Document queue QuickBooks rows (Bills/Statements) vs QuickBooks expense categories.");
    lines.push("- Document queue SoftDent rows (Claims/A/R/Production) vs SoftDent exports — not QuickBooks.");
    lines.push("");

    lines.push("Live snapshot (current program data):");
    const arAvailable = softDentReadSourceStatus(snap).arAvailable;
    if (sd) {
      const sdProd = (sd.glance || []).find((g) => g.label === "Production MTD");
      const sdColl = (sd.glance || []).find((g) => g.label === "Collections MTD");
      lines.push(
        `- SoftDent: production ${sdProd?.value || "—"}, collections ${sdColl?.value || "—"}, verified A/R ${arAvailable ? sd.hero?.value || "—" : "—"}, status ${sd.status || "—"}`,
      );
    } else {
      lines.push("- SoftDent: no dashboard data loaded.");
    }
    if (qb) {
      const qbRev = (qb.pl?.rows || []).find((r) => r.category === "Revenue");
      const qbNet = (qb.pl?.rows || []).find((r) => r.category === "Net Income");
      lines.push(
        `- QuickBooks: revenue ${qbRev?.amount || "—"}, net income ${qbNet?.amount || "—"}, sync ${qb.syncStatus || "—"}`,
      );
    } else {
      lines.push("- QuickBooks: no P&L data loaded.");
    }

    const sdDatasets = bundle.softdent || {};
    const qbDatasets = bundle.quickbooks || {};
    const sdLoaded = ["dashboard", "claims", "ar", "clinicalNotes"].filter((name) => {
      const ds = sdDatasets[name];
      return ds && Array.isArray(ds.rows) && ds.rows.length;
    });
    const qbLoaded = ["revenue", "expenses", "expenseCategories", "profitAndLoss"].filter((name) => {
      const ds = qbDatasets[name];
      return ds && Array.isArray(ds.rows) && ds.rows.length;
    });
    lines.push(`- SoftDent import files loaded: ${sdLoaded.length ? sdLoaded.join(", ") : "none"}`);
    lines.push(`- QuickBooks import files loaded: ${qbLoaded.length ? qbLoaded.join(", ") : "none"}`);

    if (docs.queueCount) {
      const counts = docs.sourceCounts || {};
      lines.push(
        "",
        `Documents page queue (${docs.queueCount} total): QuickBooks ${counts.quickbooks || 0}, SoftDent ${counts.softdent || 0}, OCR ${counts.ocr || 0}, manual ${counts.manual || 0}`,
      );
      const sample = docs.workbookSample || docs.top || [];
      const bySource = { softdent: [], quickbooks: [], ocr: [], manual: [] };
      sample.forEach((doc) => {
        const key = documentQueueSourceKey(doc);
        if (bySource[key]) bySource[key].push(doc);
      });
      ["softdent", "quickbooks", "ocr", "manual"].forEach((key) => {
        if (!bySource[key].length) return;
        const label = key === "ocr" ? "OCR inbox" : key === "manual" ? "Manual" : SOURCE_SYSTEM_PROFILES[key]?.label || key;
        lines.push(`  ${label} document rows (sample):`);
        bySource[key].slice(0, 4).forEach((doc) => {
          lines.push(`    - ${doc.id} · ${doc.vendor || "—"} · ${doc.amount || "—"} · ${doc.status || "—"}`);
        });
      });
    } else {
      lines.push("", "Documents page queue: empty — OCR inbox, manual add, or import sync needed.");
    }

    lines.push("", "HAL reads both systems locally only. Nothing is posted or written back.");
    return lines.join("\n");
  }

  function formatSourceHealthText(sourceHealth, staticItems) {
    const staticByTarget = {};
    (staticItems || []).forEach((item) => {
      if (item && item.target) staticByTarget[item.target] = item;
    });
    const labels = { softdent: "SoftDent", quickbooks: "QuickBooks", documents: "Documents", library: "Library" };
    const keys = Object.keys(sourceHealth || {}).length ? Object.keys(sourceHealth) : Object.keys(staticByTarget);
    const lines = keys.map((key) => {
      const live = (sourceHealth || {})[key] || {};
      const fallback = staticByTarget[key] || {};
      const label = fallback.label || labels[key] || key;
      const connectionStatus = live.connectionStatus || (live.hasData ? "Connected" : fallback.status || "Missing");
      if (live.hasData || live.connectionStatus) {
        const freshness = live.freshness ? ` Freshness: ${live.freshness}.` : "";
        const sync = live.syncState ? ` Sync: ${live.syncState}.` : "";
        const datasetSummary = live.datasetSummary ? ` Datasets: ${live.datasetSummary}.` : "";
        const datasetLines = Array.isArray(live.datasetLines) && live.datasetLines.length ? `\n${live.datasetLines.map((line) => `    ${line}`).join("\n")}` : "";
        return `- ${label} — ${connectionStatus}: ${live.detail || "Imported data present."}${freshness}${sync}${datasetSummary}${datasetLines}`;
      }
      const extra = fallback.freshness ? ` Freshness: ${fallback.freshness}.` : "";
      const warn = fallback.warning ? ` Warning: ${fallback.warning}` : "";
      const datasetLines = Array.isArray(live.datasetLines) && live.datasetLines.length ? `\n${live.datasetLines.map((line) => `    ${line}`).join("\n")}` : "";
      return `- ${label} — ${connectionStatus}: ${live.detail || fallback.detail || "No import data loaded yet."}${extra}${warn}${datasetLines}`;
    });
    return lines.length ? `Read-only source intake status:\n${lines.join("\n")}` : "No source intake items configured.";
  }

  function importDiagnosticsApi() {
    if (typeof ImportDiagnostics !== "undefined") return ImportDiagnostics;
    if (typeof window !== "undefined" && window.ImportDiagnostics) return window.ImportDiagnostics;
    try {
      return require("./import-diagnostics.js");
    } catch {
      return null;
    }
  }

  function systemImportHealth(bundle, system) {
    const diagApi = importDiagnosticsApi();
    const diagnostics = (bundle && bundle.diagnostics) || (diagApi && bundle ? diagApi.evaluateBundle(bundle) : null);
    if (!diagnostics || !Array.isArray(diagnostics.datasets)) {
      return { connectionStatus: "Missing", datasetSummary: "0/0 connected", datasetLines: [], detail: "No import diagnostics available." };
    }
    const items = diagnostics.datasets.filter((item) => item.system === system);
    const summary = diagApi && typeof diagApi.systemSummary === "function" ? diagApi.systemSummary(diagnostics, system) : null;
    const statusLabel = summary && diagApi ? diagApi.statusLabel(summary.status) : "Missing";
    const connected = items.filter((item) => item.status === "connected").length;
    const datasetLines = items.map((item) => {
      const label = diagApi ? diagApi.statusLabel(item.status) : item.status;
      return `${item.datasetKey}: ${label}`;
    });
    let detail = `${connected}/${items.length} datasets connected.`;
    const worst = items.find((item) => item.status === "missing" || item.status === "stale") || items.find((item) => item.status === "partial");
    if (worst && worst.detail) detail = worst.detail;
    return {
      connectionStatus: statusLabel,
      datasetSummary: `${connected}/${items.length} connected`,
      datasetLines,
      detail,
      items,
    };
  }

  /* ============================================================
   * Widgets — port of widget_builder.py + widget_feed.py
   * (import-cache widget feed derived from the program snapshot)
   * ========================================================== */

  const WIDGET_NAV = {
    practiceFinancialOverview: "financial",
    nr2KpiRibbon: "financial",
    nr2ProductionReconciliation: "financial",
    nr2CollectionLag: "financial",
    nr2GoalScorecard: "financial",
    nr2AlertTicker: "financial",
    nr2MonthlyTrendCombo: "financial",
    nr2ProviderCompensationWidget: "financial",
    softdentProductionDaily: "financial",
    softdentCollectionsDaily: "softdent",
    softdentNewPatientsMTD: "softdent",
    softdentClaimsOutstanding: "softdent",
    softdentProviderProduction: "softdent",
    softdentAppointmentsSnapshot: "softdent",
    financialProductionTrend: "financial",
    payerMixAndCollections: "financial",
    providerPerformance: "financial",
    ebitdaNormalization: "quickbooks",
    quickbooksProfitLossDetail: "quickbooks",
    quickbooksMonthlyRevenue: "quickbooks",
    quickbooksNetIncomeSummary: "quickbooks",
    quickbooksBalanceSheetSummary: "quickbooks",
    quickbooksCashFlowTrend: "quickbooks",
    quickbooksRevenueByService: "quickbooks",
    quickbooksArAging: "quickbooks",
    quickbooksExpenseBreakdown: "quickbooks",
    accountsPayableAutomation: "documents",
    documentIntakeQueue: "documents",
    documentPreview: "documents",
    periodCloseAndPosting: "documents",
    journalPostingQueue: "documents",
    smartClaimsAndReceivables: "ar",
    claimsPipeline: "claims",
    careDeliveryPerformance: "softdent",
    softdentArAging: "softdent",
    softdentResponsibility: "softdent",
    newPatients: "softdent",
    treatmentPlanSummary: "softdent",
    caseAcceptance: "softdent",
    hygieneRecall: "softdent",
    softdentOperatoryGrid: "softdent",
    arAgingAndCollections: "ar",
    arOutstandingClaims: "ar",
    narrativeWorkflow: "narratives",
    documentLibrary: "library",
    officeManagerPriorities: "office-manager",
    officeManagerSurfaces: "office-manager",
    halAskHal: "hal",
    halMorningBriefing: "hal",
    halSituationalHero: "hal",
    sidenotesProgram: "hal",
    halImportHealth: "hal",
    halCommandPalette: "hal",
  };

  const WIDGET_ORDER = [
    "practiceFinancialOverview",
    "nr2KpiRibbon",
    "nr2ProductionReconciliation",
    "nr2CollectionLag",
    "nr2GoalScorecard",
    "nr2AlertTicker",
    "nr2MonthlyTrendCombo",
    "nr2ProviderCompensationWidget",
    "softdentProductionDaily",
    "financialProductionTrend",
    "payerMixAndCollections",
    "providerPerformance",
    "ebitdaNormalization",
    "quickbooksProfitLossDetail",
    "quickbooksMonthlyRevenue",
    "quickbooksNetIncomeSummary",
    "quickbooksBalanceSheetSummary",
    "quickbooksCashFlowTrend",
    "quickbooksRevenueByService",
    "quickbooksArAging",
    "quickbooksExpenseBreakdown",
    "accountsPayableAutomation",
    "documentIntakeQueue",
    "documentPreview",
    "periodCloseAndPosting",
    "journalPostingQueue",
    "smartClaimsAndReceivables",
    "claimsPipeline",
    "arAgingAndCollections",
    "arOutstandingClaims",
    "careDeliveryPerformance",
    "softdentArAging",
    "softdentResponsibility",
    "newPatients",
    "treatmentPlanSummary",
    "caseAcceptance",
    "hygieneRecall",
    "softdentOperatoryGrid",
    "softdentCollectionsDaily",
    "softdentNewPatientsMTD",
    "softdentClaimsOutstanding",
    "softdentProviderProduction",
    "softdentAppointmentsSnapshot",
    "narrativeWorkflow",
    "documentLibrary",
    "halMorningBriefing",
    "halSituationalHero",
    "halAskHal",
    "sidenotesProgram",
    "halImportHealth",
  ];

  const WIDGET_FILL_REQUIREMENTS = {
    practiceFinancialOverview: ["SoftDent dashboard export with production/collections", "QuickBooks revenue/P&L export"],
    nr2KpiRibbon: ["SoftDent dashboard export", "QuickBooks monthly P&L rows", "Optional SoftDent A/R aging for DSO"],
    nr2ProductionReconciliation: ["SoftDent dashboard monthly production rows", "QuickBooks monthly revenue/P&L rows with matching periods"],
    nr2CollectionLag: ["SoftDent A/R aging export for weighted DSO", "Or SoftDent dashboard production/collections for monthly proxy"],
    nr2GoalScorecard: ["SoftDent dashboard production rows for YTD actuals", "Optional NR2_GOAL_PRODUCTION_YTD env override"],
    nr2AlertTicker: ["SoftDent dashboard + QuickBooks P&L for variance alerts", "SoftDent A/R aging for 90+ bucket warnings"],
    nr2MonthlyTrendCombo: ["SoftDent dashboard monthly production/collections", "QuickBooks monthly revenue rows"],
    nr2ProviderCompensationWidget: ["SoftDent provider production rows or sd_procedures ODBC extract"],
    softdentProductionDaily: ["SoftDent sd_procedures table (ODBC extract)", "Or daysheet/dashboard JSON fallback"],
    financialProductionTrend: ["SoftDent dashboard export with current period production", "Period labels for trend comparison"],
    payerMixAndCollections: ["SoftDent collections and payer mix fields", "Verified collection-rate source"],
    providerPerformance: ["SoftDent dashboard export for Dr. Michael Reno"],
    ebitdaNormalization: ["QuickBooks expenses export", "Staff-reviewed EBITDA add-back categories"],
    quickbooksProfitLossDetail: ["QuickBooks revenue/P&L export", "QuickBooks expenses export"],
    quickbooksMonthlyRevenue: ["QuickBooks revenue/P&L export with monthly TotalIncome rows"],
    quickbooksNetIncomeSummary: ["QuickBooks monthly P&L rows with NetIncome"],
    quickbooksBalanceSheetSummary: ["QuickBooks A/R export", "QuickBooks revenue/P&L for equity proxy"],
    quickbooksCashFlowTrend: ["QuickBooks monthly P&L rows (income/expense by period)"],
    quickbooksRevenueByService: ["QuickBooks expense categories or revenue proxy from P&L"],
    quickbooksArAging: ["QuickBooks A/R export or SDK probe ar_aging"],
    quickbooksExpenseBreakdown: ["QuickBooks expense category export", "QuickBooks monthly expenses"],
    accountsPayableAutomation: ["Local accounting document queue", "QuickBooks expenses or vendor document imports"],
    documentIntakeQueue: ["SoftDent and QuickBooks financial summary rows synced into the document queue", "Optional manual Add document entries"],
    documentPreview: ["Selected local document metadata and extracted fields"],
    periodCloseAndPosting: ["Accounting document period assignment", "Human-reviewed posting readiness"],
    journalPostingQueue: ["Desktop journal posting queue (SQLite)", "Reviewed accruals ready for export"],
    smartClaimsAndReceivables: ["SoftDent claims export", "Verified SoftDent A/R export"],
    claimsPipeline: ["SoftDent claims export with claim status values"],
    arAgingAndCollections: ["Verified SoftDent A/R aging export"],
    arOutstandingClaims: ["SoftDent claims export with balances or verified A/R export"],
    careDeliveryPerformance: ["SoftDent dashboard export", "Verified patient balance/A/R source"],
    softdentArAging: ["Verified SoftDent A/R aging export"],
    softdentResponsibility: ["SoftDent dashboard export with insurance and patient responsibility values"],
    newPatients: ["SoftDent new patient export (analytics sync via softdent_practice_exports.py when tables exist)"],
    treatmentPlanSummary: ["SoftDent treatment_plan_summary.csv (analytics sync via softdent_practice_exports.py when tables exist)"],
    caseAcceptance: ["SoftDent case acceptance export or derived treatment plan summary"],
    hygieneRecall: ["SoftDent hygiene_recall_summary.csv (analytics sync via softdent_practice_exports.py when tables exist)"],
    softdentOperatoryGrid: ["SoftDent operatory schedule export (operatory_schedule.json → operatoryChairs[])"],
    softdentCollectionsDaily: ["sd_payments ODBC extract", "Or SoftDent dashboard collections rows"],
    softdentNewPatientsMTD: ["sd_patients first_visit_date", "Or softdent_new_patients.csv export"],
    softdentClaimsOutstanding: ["sd_claims table", "Or softdent_claims_export.csv"],
    softdentProviderProduction: ["sd_procedures grouped by provider", "Or financial dashboard provider rows"],
    softdentAppointmentsSnapshot: ["sd_appointments", "Or operatoryChairs[] schedule export"],
    narrativeWorkflow: ["Local narrative drafts or claim source facts from SoftDent claims"],
    documentLibrary: ["Local library documents or indexed document metadata"],
    halImportHealth: ["Import bundle diagnostics", "SoftDent and QuickBooks dataset contracts"],
  };

  function widgetContractApi() {
    if (typeof WidgetContract !== "undefined") return WidgetContract;
    if (typeof window !== "undefined" && window.WidgetContract) return window.WidgetContract;
    try {
      return require("./widget-contract.js");
    } catch {
      return null;
    }
  }

  function buildContractContext(snapshot, dashboards) {
    const diagApi =
      typeof ImportDiagnostics !== "undefined"
        ? ImportDiagnostics
        : typeof window !== "undefined" && window.ImportDiagnostics
          ? window.ImportDiagnostics
          : null;
    const bundle = snapshot && snapshot.importBundle;
    let diagnostics = bundle && bundle.diagnostics;
    if (!diagnostics && bundle && diagApi && typeof diagApi.evaluateBundle === "function") {
      diagnostics = diagApi.evaluateBundle(bundle);
    }
    return {
      dashboards: dashboards || snapshot.dashboards || {},
      diagnostics,
      importBundle: bundle || null,
    };
  }

  function buildContractWidget(widgetKey, contractCtx, fallbackStatus, summary) {
    const contract = widgetContractApi();
    if (!contract) return null;
    const built = contract.buildWidgetMetrics(widgetKey, contractCtx);
    if (!built.contract) return null;
    const status = contract.widgetStatusFromStates(built.states);
    const resolvedStatus =
      status === "SUCCESS"
        ? status
        : status === "FAILED"
          ? "FAILED"
          : fallbackStatus === "SUCCESS"
            ? "DEGRADED"
            : status;
    return {
      key: widgetKey,
      title: built.contract.title || widgetKey,
      status: resolvedStatus,
      summary,
      navTarget: built.contract.navTarget || WIDGET_NAV[widgetKey],
      metrics: built.metrics,
      metricStates: built.states,
    };
  }

  function plAmount(dashboard, category) {
    const row = ((dashboard && dashboard.pl && dashboard.pl.rows) || []).find((r) => r.category === category);
    return row ? row.amount || null : null;
  }

  function glanceValue(dashboard, label) {
    const row = ((dashboard && dashboard.glance) || []).find((g) => g.label === label);
    return row ? row.value || null : null;
  }

  function metricValue(value) {
    if (value === null || value === undefined || value === "") return null;
    return value;
  }

  function kpiValue(kpis, label) {
    const row = (kpis || []).find((k) => String(k.label || "").toLowerCase() === String(label || "").toLowerCase());
    return row ? metricValue(row.value) : null;
  }

  function sumCounts(rows) {
    if (!Array.isArray(rows) || !rows.length) return null;
    const total = rows.reduce((acc, row) => acc + (Number(row.count) || 0), 0);
    return total > 0 ? total : null;
  }

  function lastSeriesValue(series) {
    if (!series) return null;
    const values = Array.isArray(series) ? series : series.values;
    if (!Array.isArray(values) || !values.length) return null;
    return metricValue(values[values.length - 1]);
  }

  function firstItem(items) {
    return Array.isArray(items) && items.length ? items[0] : null;
  }

  function healthyCount(rows) {
    if (!Array.isArray(rows) || !rows.length) return null;
    return rows.filter((row) => row && row.ok !== false && !/fail|error|blocked/i.test(String(row.value || row.status || ""))).length;
  }

  function rowAmount(rows, label) {
    const row = (rows || []).find((r) => String(r.category || r.label || "").toLowerCase() === String(label || "").toLowerCase());
    return row ? metricValue(row.amount || row.value) : null;
  }

  function mergeWidgetStatus() {
    const statuses = Array.prototype.slice.call(arguments).filter(Boolean);
    if (!statuses.length) return "FAILED";
    if (statuses.every((s) => s === "SUCCESS")) return "SUCCESS";
    if (statuses.some((s) => s === "SUCCESS")) return "DEGRADED";
    return "FAILED";
  }

  function publishJobStatus(widgets) {
    const statuses = Object.values(widgets).map((w) => String(w.status || "").toUpperCase());
    if (statuses.length && statuses.every((s) => s === "SUCCESS")) return "SUCCESS";
    if (statuses.some((s) => s === "SUCCESS")) return "DEGRADED";
    return "FAILED";
  }

  function parseMetricNumber(value) {
    if (value === null || value === undefined || value === "" || value === "—" || value === "Not Configured") return null;
    if (typeof value === "number") return Number.isFinite(value) ? value : null;
    const raw = String(value).replace(/[$,%\s,]/g, "");
    if (!raw || raw === "-" || raw === "—") return null;
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function nearlyEqual(a, b, tolerance) {
    if (a === null || b === null) return true;
    const allowed = Math.max(Number(tolerance) || 1, Math.abs(a) * 0.01, Math.abs(b) * 0.01);
    return Math.abs(a - b) <= allowed;
  }

  function ratioDiff(a, b) {
    if (a === null || b === null) return 0;
    const denom = Math.max(Math.abs(a), Math.abs(b), 1);
    return Math.abs(a - b) / denom;
  }

  function addCommitIssue(issues, widgetKey, metricKey, severity, message) {
    issues.push({ widgetKey, metricKey, severity, message });
  }

  const FINANCIAL_QUALITY_OVERALL_PASS_FAILED =
    "Financial data quality overallPass failed — resolve import freshness, collections, period alignment, or QuickBooks reconcile before period close.";
  const FINANCIAL_QUALITY_SCORE_MISSING =
    "Financial dashboard loaded without a quality score — run import diagnostics before period close.";

  function degradeWidgetForCommitValidation(feed, issue) {
    const widget = feed.widgets && feed.widgets[issue.widgetKey];
    if (!widget) return;
    widget.commitValidation = widget.commitValidation || { status: "PASS", issues: [] };
    widget.commitValidation.issues.push(issue);
    widget.commitValidation.status = "REVIEW";
    if (issue.severity === "warning" && String(widget.status || "").toUpperCase() === "SUCCESS") {
      widget.status = "DEGRADED";
    }
  }

  function applyAccountingExcelCommitValidation(feed, snapshot) {
    if (!feed || !feed.widgets) return feed;
    const widgets = feed.widgets;
    const issues = [];
    const finDash = snapshot.dashboards && snapshot.dashboards.financial;
    const overview = widgets.practiceFinancialOverview && widgets.practiceFinancialOverview.metrics;
    const qbDetail = widgets.quickbooksProfitLossDetail && widgets.quickbooksProfitLossDetail.metrics;
    const payer = widgets.payerMixAndCollections && widgets.payerMixAndCollections.metrics;
    const treatment = widgets.treatmentPlanSummary && widgets.treatmentPlanSummary.metrics;
    const caseAcceptance = widgets.caseAcceptance && widgets.caseAcceptance.metrics;

    if (overview) {
      const revenue = parseMetricNumber(overview.monthlyRevenue);
      const netIncome = parseMetricNumber(overview.monthlyNetIncome);
      const production = parseMetricNumber(overview.productionTotal);
      const collections = parseMetricNumber(overview.collectionsTotal);
      const expenses = parseMetricNumber((snapshot.dashboards?.quickbooks || {}).expenses);
      if (
        production !== null &&
        collections !== null &&
        collections === 0 &&
        production > 0 &&
        !(finDash && (finDash.collectionsPending || finDash.collectionsMissing || finDash.collectionsZeroWithProduction))
      ) {
        addCommitIssue(
          issues,
          "practiceFinancialOverview",
          "collectionsTotal",
          "warning",
          "Collections not reported for this period — verify daysheet export; this is not a true 0% rate.",
        );
      }
      if (revenue !== null && expenses !== null && netIncome !== null && !nearlyEqual(revenue - expenses, netIncome, 1)) {
        addCommitIssue(
          issues,
          "practiceFinancialOverview",
          "monthlyNetIncome",
          "warning",
          "QuickBooks revenue minus expenses does not reconcile to net income.",
        );
      }
      if (production !== null && collections !== null && collections > production * 1.15) {
        addCommitIssue(
          issues,
          "practiceFinancialOverview",
          "collectionsTotal",
          "warning",
          "SoftDent collections are more than 115% of production for the period.",
        );
      }
      if (revenue !== null && collections !== null && ratioDiff(revenue, collections) > 0.4) {
        addCommitIssue(
          issues,
          "practiceFinancialOverview",
          "monthlyRevenue",
          "info",
          "QuickBooks revenue and SoftDent collections differ by more than 40%; verify period alignment.",
        );
      }
    }

    if (finDash && finDash.collectionsMissing) {
      addCommitIssue(
        issues,
        "practiceFinancialOverview",
        "collectionsTotal",
        "warning",
        "SoftDent collections are not reported for the current dashboard period.",
      );
    } else if (finDash && finDash.collectionsPending) {
      addCommitIssue(
        issues,
        "practiceFinancialOverview",
        "collectionsTotal",
        "info",
        "SoftDent collections export is pending for the QuickBooks-comparable period; production is loaded from provider totals.",
      );
    }
    if (finDash && finDash.collectionsZeroWithProduction && !finDash.collectionsPending) {
      addCommitIssue(
        issues,
        "practiceFinancialOverview",
        "collectionsTotal",
        "warning",
        "Latest SoftDent period shows $0 collections with production — verify final daysheet export; this is not a true 0% rate.",
      );
      addCommitIssue(
        issues,
        "practiceFinancialOverview",
        "collectionsTotal",
        "warning",
        "Import quality is reduced because collection health failed on the latest SoftDent period.",
      );
    }
    if (finDash && finDash.periodAlignment && finDash.periodAlignment.aligned === false && finDash.periodAlignment.message) {
      addCommitIssue(
        issues,
        "practiceFinancialOverview",
        "monthlyRevenue",
        "warning",
        finDash.periodAlignment.message,
      );
    }
    if (finDash && finDash.quality && finDash.quality.overallPass === false) {
      addCommitIssue(
        issues,
        "practiceFinancialOverview",
        "monthlyRevenue",
        "warning",
        FINANCIAL_QUALITY_OVERALL_PASS_FAILED,
      );
    } else if (
      finDash &&
      (finDash.dataSource === "import" || finDash.dataSource === "persisted") &&
      !finDash.quality
    ) {
      addCommitIssue(issues, "practiceFinancialOverview", "monthlyRevenue", "warning", FINANCIAL_QUALITY_SCORE_MISSING);
    }

    const qbDash = snapshot.dashboards && snapshot.dashboards.quickbooks;
    if (qbDash && qbDash.expenseCategories && qbDash.expenseCategories.scope === "unlabeled") {
      addCommitIssue(
        issues,
        "ebitdaNormalization",
        "expenseCategoriesTotal",
        "info",
        "Expense category pivot has no period column — total may be cumulative; compare to monthly P&L expenses before period close.",
      );
    }

    if (finDash && finDash.collectionRateMetrics && finDash.collectionRateMetrics.latestMonthIncomplete) {
      addCommitIssue(
        issues,
        "payerMixAndCollections",
        "latestMonthCollectionRate",
        "info",
        `Latest month ${finDash.collectionRateMetrics.latestMonthPeriod} is incomplete ($0 or missing collections). Use trailing rate (${finDash.collectionRateMetrics.trailingRate || "n/a"}) for period-close review.`,
      );
    }

    const arCross = finDash && finDash.arCrossCheck;
    if (arCross && arCross.comparable && arCross.withinTolerance === false) {
      addCommitIssue(issues, "arAgingAndCollections", "arCrossSourceVariance", "warning", arCross.message);
    } else if (arCross && !arCross.comparable && arCross.softdentTotal != null) {
      addCommitIssue(issues, "arAgingAndCollections", "quickbooksArTotal", "info", arCross.message);
    }

    if (qbDetail) {
      const revenue = parseMetricNumber(qbDetail.revenue);
      const cogs = parseMetricNumber(qbDetail.cogs);
      const grossProfit = parseMetricNumber(qbDetail.grossProfit);
      const operatingExpenses = parseMetricNumber(qbDetail.operatingExpenses);
      const netIncome = parseMetricNumber(qbDetail.netIncome);
      if (qbDash && qbDash.plReconcile && qbDash.plReconcile.matches === false) {
        addCommitIssue(
          issues,
          "quickbooksProfitLossDetail",
          "netIncome",
          "warning",
          "QuickBooks P&L net income does not match revenue minus expenses from import files.",
        );
      }
      if (revenue !== null && cogs !== null && grossProfit !== null && !nearlyEqual(revenue - cogs, grossProfit, 1)) {
        addCommitIssue(issues, "quickbooksProfitLossDetail", "grossProfit", "warning", "QuickBooks gross profit does not equal revenue minus COGS.");
      }
      if (grossProfit !== null && operatingExpenses !== null && netIncome !== null && !nearlyEqual(grossProfit - operatingExpenses, netIncome, 1)) {
        addCommitIssue(issues, "quickbooksProfitLossDetail", "netIncome", "warning", "QuickBooks net income does not equal gross profit minus operating expenses.");
      }
    }

    if (payer) {
      const rate = parseMetricNumber(payer.collectionRate);
      const topShare = parseMetricNumber(payer.topPayerShare);
      if (rate !== null && (rate < 0 || rate > 100)) {
        addCommitIssue(issues, "payerMixAndCollections", "collectionRate", "warning", "Collection rate must be between 0% and 100%.");
      }
      if (topShare !== null && (topShare < 0 || topShare > 100)) {
        addCommitIssue(issues, "payerMixAndCollections", "topPayerShare", "warning", "Top payer share must be between 0% and 100%.");
      }
    }

    if (treatment) {
      const presented = parseMetricNumber(treatment.plansPresented);
      const accepted = parseMetricNumber(treatment.plansAccepted);
      if (presented !== null && accepted !== null && accepted > presented) {
        addCommitIssue(issues, "treatmentPlanSummary", "plansAccepted", "warning", "Accepted treatment plans cannot exceed presented treatment plans.");
      }
    }

    if (caseAcceptance) {
      const rate = parseMetricNumber(caseAcceptance.acceptanceRate);
      const accepted = parseMetricNumber(caseAcceptance.acceptedCount);
      const presented = parseMetricNumber(caseAcceptance.presentedCount);
      if (rate !== null && (rate < 0 || rate > 100)) {
        addCommitIssue(issues, "caseAcceptance", "acceptanceRate", "warning", "Case acceptance rate must be between 0% and 100%.");
      }
      if (accepted !== null && presented !== null && accepted > presented) {
        addCommitIssue(issues, "caseAcceptance", "acceptedCount", "warning", "Accepted cases cannot exceed presented cases.");
      }
    }

    const docs = snapshot && snapshot.documents;
    const docQueue = widgets.documentIntakeQueue;
    if (docs && docQueue && docs.queueCount > 0) {
      const pendingDocs = (docs.top || []).filter((doc) => String(doc.status || "").toLowerCase().includes("pending"));
      if (pendingDocs.length && docs.queueCount >= 3) {
        addCommitIssue(
          issues,
          "documentIntakeQueue",
          "queueCount",
          "info",
          `${pendingDocs.length} visible document(s) are still Pending Review; reconcile against QuickBooks expenses before posting.`,
        );
      }
    }

    Object.values(widgets).forEach((widget) => {
      if (!widget) return;
      widget.commitValidation = widget.commitValidation || { status: "PASS", issues: [] };
    });
    issues.forEach((issue) => degradeWidgetForCommitValidation(feed, issue));
    const warningCount = issues.filter((issue) => issue.severity === "warning").length;
    feed.accountingExcelValidation = {
      status: warningCount ? "REVIEW" : "PASS",
      checkedAt: feed.generatedAt || new Date().toISOString(),
      checks: [
        "QuickBooks P&L arithmetic",
        "Revenue/expense/net-income reconciliation",
        "SoftDent production/collections reasonableness",
        "Percent and count bounds",
        "Treatment-plan and case-acceptance consistency",
      ],
      issues,
    };
    return feed;
  }

  function importHealthWidgetStatus(diagnostics) {
    const datasets = (diagnostics && diagnostics.datasets) || [];
    if (!datasets.length) return "FAILED";
    const blocking = datasets.filter((row) => {
      const severity = String(row.severity || "warning");
      if (severity === "optional") return false;
      const status = String(row.status || "");
      if (severity === "warning" && (status === "missing" || status === "stale")) return false;
      return status === "missing" || status === "stale" || (status !== "connected" && severity === "critical");
    });
    if (!blocking.length) return "SUCCESS";
    return datasets.some((row) => row.status === "connected") ? "DEGRADED" : "FAILED";
  }

  function buildImportHealthWidget(bundle) {
    const diagnostics = (bundle && bundle.diagnostics) || null;
    const summary = (diagnostics && diagnostics.summary) || {};
    const datasets = (diagnostics && diagnostics.datasets) || [];
    const optionalMissing = datasets.filter(
      (row) => row.status === "missing" && String(row.severity || "") === "optional",
    ).length;
    return {
      key: "halImportHealth",
      title: "Import & Source Health",
      status: importHealthWidgetStatus(diagnostics),
      summary:
        "Import-mode dataset health across SoftDent and QuickBooks contracts. Optional exports do not block a healthy import posture.",
      navTarget: WIDGET_NAV.halImportHealth,
      metrics: {
        connectedDatasets: metricValue(summary.connected),
        partialDatasets: metricValue(summary.partial),
        missingDatasets: metricValue(summary.missing),
        optionalMissing: metricValue(optionalMissing || null),
      },
    };
  }

  function crossReconcileSkill(snapshot) {
    const analytics = buildAnalyticsPack(snapshot);
    const qb = buildQbReportsPack(snapshot);
    const importWidget = buildImportHealthWidget(snapshot && snapshot.importBundle);
    const recon = analytics.recon || { hasData: false, latest: null };
    const net = qb.netIncome || { hasData: false };
    const ribbon = analytics.ribbon || { tiles: [], hasData: false };
    const lag = analytics.lag || { hasData: false };
    const domains = [];
    const actuators = [];
    let risk = null;
    let opportunity = null;

    if (recon.hasData && recon.latest) {
      domains.push("production");
      const variance = recon.latest.variancePct;
      const period = recon.latest.period || "latest period";
      if (variance != null) {
        const abs = Math.abs(variance);
        if (abs > 10) {
          risk = `Production vs QuickBooks revenue diverged ${variance}% in ${period}`;
          actuators.push({ label: "Review reconciliation", actionId: "navigate", target: "financial" });
        } else if (abs <= 3) {
          opportunity = `Production and QuickBooks aligned within ${abs}% for ${period}`;
        }
      }
    }

    if (net.hasData) {
      domains.push("expenses");
      if (net.latestNetIncome != null && net.latestNetIncome < 0) {
        risk =
          risk ||
          `Net income is negative (${net.latestNetIncome}) for ${net.latestMonth || "latest month"}`;
        actuators.push({ label: "Open QuickBooks summary", actionId: "navigate", target: "quickbooks" });
      } else if (net.latestNetIncome > 0 && !opportunity) {
        opportunity = `Net income ${net.latestNetIncome} for ${net.latestMonth || "latest month"}`;
      }
    }

    if (importWidget.status !== "SUCCESS") {
      domains.push("imports");
      const missing = importWidget.metrics && importWidget.metrics.missingDatasets;
      const missingCount = missing != null && missing !== "—" ? Number(missing) : 0;
      if (missingCount > 0) {
        risk = risk || `${missingCount} import dataset(s) missing — cross-domain widgets may be incomplete`;
        actuators.push({ label: "Sync imports now?", actionId: "refresh-imports", requiresConsent: true });
      }
    }

    if (lag.hasData && lag.avgLagDays != null && lag.avgLagDays > 45) {
      domains.push("collections");
      risk = risk || `Collection lag at ${lag.avgLagDays} days — cash flow risk`;
    }

    const collTile = (ribbon.tiles || []).find((tile) => tile.label === "Collections vs QB");
    if (collTile && collTile.tone === "alert") {
      domains.push("collections");
      risk =
        risk ||
        `SoftDent collections vs QuickBooks revenue variance ${collTile.value} — investigate deposit timing`;
      actuators.push({ label: "Review collection lag", actionId: "navigate", target: "softdent" });
    } else if (collTile && collTile.tone === "warn" && !opportunity) {
      opportunity = `Collections vs QuickBooks within watch band (${collTile.value})`;
    }

    const depVar = analytics.depositVariance || {};
    const depThreshold = depVar.thresholdPct != null ? Number(depVar.thresholdPct) : 8;
    if (depVar.hasData && depVar.variancePct != null && Math.abs(depVar.variancePct) > depThreshold) {
      domains.push("collections");
      risk =
        risk ||
        `SoftDent collections vs QuickBooks bank deposits diverged ${depVar.variancePct}% in ${depVar.period || "latest period"}`;
      actuators.push({ label: "Review deposit reconciliation", actionId: "navigate", target: "financial" });
    } else if (depVar.hasData && depVar.variancePct != null && !opportunity) {
      opportunity = `Collections and QuickBooks deposits aligned within ${depThreshold}% for ${depVar.period || "latest period"}`;
    }

    let sentence;
    if (risk && opportunity) {
      sentence = `${risk}; however, ${opportunity.charAt(0).toLowerCase()}${opportunity.slice(1)}.`;
    } else if (risk) {
      sentence = `${risk} — review cross-domain metrics before decisions.`;
    } else if (opportunity) {
      sentence = `${opportunity} — imports and KPIs look steady across domains.`;
    } else if (domains.length >= 2) {
      sentence = `Cross-check: ${domains.join(" + ")} data loaded; no urgent variance flagged.`;
    } else {
      sentence =
        "Morning briefing pending — import SoftDent and QuickBooks data for cross-domain synthesis.";
      actuators.push({ label: "Refresh imports", actionId: "refresh-imports", requiresConsent: true });
    }

    return {
      sentence,
      domains: [...new Set(domains)],
      risk,
      opportunity,
      importHealthStatus: importWidget.status,
      importHealthSummary: importWidget.summary,
      kpiTiles: (ribbon.tiles || []).slice(0, 4),
      actuators,
      reconSummary: recon.summary || "",
      netIncomeLatest: net.latestNetIncome != null ? net.latestNetIncome : null,
    };
  }

  function buildAnalyticsPack(snapshot) {
    const api =
      typeof NR2Analytics !== "undefined"
        ? NR2Analytics
        : typeof window !== "undefined" && window.NR2Analytics
          ? window.NR2Analytics
          : null;
    if (!api) {
      return {
        recon: { rows: [], hasData: false, latest: null },
        lag: { hasData: false, avgLagDays: null },
        qbRev: { hasData: false, values: [], labels: [] },
        prodDaily: { hasData: false, points: [] },
        ribbon: { tiles: [], hasData: false },
        goal: { hasData: false, ytdProduction: null, targetProduction: null, pctOfGoal: null },
        alerts: { items: [], hasData: false },
        provComp: { providers: [], hasData: false, totalProduction: 0 },
        combo: { labels: [], hasData: false },
      };
    }
    return {
      recon: api.productionReconciliation(snapshot),
      lag: api.collectionLag(snapshot),
      qbRev: api.quickbooksMonthlyRevenue(snapshot),
      prodDaily: api.softdentProductionDaily(snapshot),
      ribbon: api.kpiRibbon(snapshot),
      depositVariance: api.collectionDepositVariance ? api.collectionDepositVariance(snapshot) : { hasData: false },
      goal: api.goalScorecard ? api.goalScorecard(snapshot) : { hasData: false },
      alerts: api.alertTicker ? api.alertTicker(snapshot) : { items: [], hasData: false },
      provComp: api.providerCompensation ? api.providerCompensation(snapshot) : { providers: [], hasData: false },
      combo: api.monthlyTrendCombo ? api.monthlyTrendCombo(snapshot) : { labels: [], hasData: false },
    };
  }

  function buildQbReportsPack(snapshot) {
    const api =
      typeof NR2QbReports !== "undefined"
        ? NR2QbReports
        : typeof window !== "undefined" && window.NR2QbReports
          ? window.NR2QbReports
          : null;
    if (!api) {
      return {
        netIncome: { hasData: false },
        balanceSheet: { hasData: false, assets: [] },
        cashFlow: { hasData: false, labels: [] },
        revenueSvc: { hasData: false, slices: [] },
        arAging: { hasData: false, buckets: [] },
      };
    }
    return {
      netIncome: api.netIncomeSummary(snapshot),
      balanceSheet: api.balanceSheetSummary(snapshot),
      cashFlow: api.cashFlowTrend(snapshot),
      revenueSvc: api.revenueByService(snapshot),
      arAging: api.arAging(snapshot),
    };
  }

  function buildSoftdentDailyPack(snapshot) {
    const api =
      typeof NR2SoftdentDaily !== "undefined"
        ? NR2SoftdentDaily
        : typeof window !== "undefined" && window.NR2SoftdentDaily
          ? window.NR2SoftdentDaily
          : null;
    if (!api) {
      return {
        collections: { hasData: false },
        newPatients: { hasData: false, count: 0 },
        claims: { hasData: false, claims: [] },
        providers: { hasData: false, providers: [] },
        appointments: { hasData: false, appointments: [] },
      };
    }
    return {
      collections: api.collectionsDaily(snapshot),
      newPatients: api.newPatientsMtd(snapshot),
      claims: api.claimsOutstanding(snapshot),
      providers: api.providerProduction(snapshot),
      appointments: api.appointmentsSnapshot(snapshot),
    };
  }

  function buildWidgetFeed(snapshot) {
    const snap = snapshot || {};
    const dashboards = snap.dashboards || {};
    const sdStatus = softDentReadSourceStatus(snap);
    const arAvailable = sdStatus.arAvailable;
    const claims = snap.claims || {};

    // A dashboard object always exists (empty shells are returned for missing
    // sources), so health must be judged by whether real import data is present
    // — not by mere object existence — or empty widgets falsely read SUCCESS.
    const dashHasData = (d) => Boolean(d && (d.dataSource === "import" || d.dataSource === "persisted"));
    const dashPartial = (d) => Boolean(d && (d.importDepth === "partial" || d.importDepth === "degraded"));
    const widgetStatusFromDash = (d) => {
      if (!dashHasData(d)) return "FAILED";
      if (dashPartial(d)) return "DEGRADED";
      return "SUCCESS";
    };
    const financialStatus = widgetStatusFromDash(dashboards.financial);
    const qbStatus = dashHasData(dashboards.quickbooks)
      ? dashPartial(dashboards.quickbooks) || /(blocked|stale)/i.test(String(dashboards.quickbooks.syncStatus || ""))
        ? "DEGRADED"
        : "SUCCESS"
      : "FAILED";
    const softdentStatus = widgetStatusFromDash(dashboards.softdent);
    const claimsStatus = claims.total > 0 ? (arAvailable ? "SUCCESS" : "DEGRADED") : "FAILED";
    const careStatus = softdentStatus === "SUCCESS" && !arAvailable ? "DEGRADED" : softdentStatus;
    const pendingPosting = ((snap.documents && snap.documents.posting) || []).reduce(
      (acc, p) => (/pending/i.test(p.label) ? acc + (p.count || 0) : acc),
      0,
    );
    const fin = dashboards.financial || {};
    const sd = dashboards.softdent || {};
    const qb = dashboards.quickbooks || {};
    const collectionHealthDegraded = Boolean(
      (fin.collectionsMissing && !fin.collectionsPending) ||
        (fin.collectionsZeroWithProduction && !fin.collectionsPending) ||
        ((fin.dataSource === "import" || fin.dataSource === "persisted") && !fin.quality) ||
        ((fin.quality && fin.quality.categories) || []).some(
          (category) => category.label === "Collection health" && Number(category.score) < 15,
        ),
    );
    const financialQualityStatus = collectionHealthDegraded
      ? "DEGRADED"
      : financialStatus;
    const arDash = dashboards.ar || {};
    const practiceDash = dashboards.practice || {};
    const contractCtx = buildContractContext(snap, {
      financial: fin,
      softdent: sd,
      quickbooks: qb,
      ar: arDash,
      practice: practiceDash,
    });
    const analyticsPack = buildAnalyticsPack(snap);
    const qbReportsPack = buildQbReportsPack(snap);
    const sdDailyPack = buildSoftdentDailyPack(snap);
    const reconComparable = (analyticsPack.recon.rows || []).filter(
      (row) => row.quickbooksRevenue != null && row.softdentProduction > 0,
    );
    const reconStatus =
      reconComparable.length >= 2
        ? "SUCCESS"
        : reconComparable.length === 1 || analyticsPack.recon.hasData
          ? "DEGRADED"
          : mergeWidgetStatus(softdentStatus, qbStatus) === "FAILED"
            ? "FAILED"
            : "DEGRADED";
    const lagStatus = analyticsPack.lag.hasData
      ? analyticsPack.lag.dsoProxy
        ? "SUCCESS"
        : "DEGRADED"
      : arAvailable
        ? "DEGRADED"
        : "FAILED";
    const qbRevStatus = analyticsPack.qbRev.hasData ? qbStatus : qbStatus === "SUCCESS" ? "DEGRADED" : "FAILED";
    const prodDailyStatus = analyticsPack.prodDaily.hasData ? softdentStatus : softdentStatus === "SUCCESS" ? "DEGRADED" : "FAILED";
    const ribbonStatus = analyticsPack.ribbon.hasData
      ? mergeWidgetStatus(reconStatus, lagStatus, qbRevStatus, prodDailyStatus)
      : "FAILED";
    const docs = snap.documents || {};
    const claimsSnap = snap.claims || {};
    const narratives = snap.narratives || {};
    const library = snap.library || {};
    const overviewWidget = buildContractWidget(
      "practiceFinancialOverview",
      contractCtx,
      mergeWidgetStatus(qbStatus, softdentStatus),
      "QuickBooks revenue reflects cash-basis deposits; SoftDent production/collections are operational PMS metrics. Compare collections to QB revenue — not production. Dental A/R is not sourced from QuickBooks.",
    );
    if (overviewWidget) {
      overviewWidget.metricLabels = WIDGET_METRIC_LABELS.practiceFinancialOverview;
      if (collectionHealthDegraded) overviewWidget.status = "DEGRADED";
    }
    const trendWidget = buildContractWidget(
      "financialProductionTrend",
      contractCtx,
      financialStatus,
      "Production trend and year-to-date production/collections indicators from the financial dashboard cache.",
    );
    const payerWidget = buildContractWidget(
      "payerMixAndCollections",
      contractCtx,
      financialStatus,
      "Payer mix, collection rate, and top payer share from the owner financial dashboard.",
    );
    const providerWidget = buildContractWidget(
      "providerPerformance",
      contractCtx,
      financialStatus,
      "Provider production split from the owner financial dashboard.",
    );
    const practiceStatus = widgetStatusFromDash(practiceDash);
    const practiceConfigured = (practiceDash && practiceDash.configured) || {};
    const newPatientsWidget = buildContractWidget(
      "newPatients",
      contractCtx,
      practiceConfigured.newPatients ? practiceStatus : "FAILED",
      "New patient counts from SoftDent when an export is configured.",
    );
    const treatmentWidget = buildContractWidget(
      "treatmentPlanSummary",
      contractCtx,
      practiceConfigured.treatmentPlans ? practiceStatus : "FAILED",
      "Treatment plan presented/accepted summary from SoftDent when an export is configured.",
    );
    const caseAcceptanceWidget = buildContractWidget(
      "caseAcceptance",
      contractCtx,
      practiceConfigured.caseAcceptance ? practiceStatus : "FAILED",
      "Case acceptance rate from SoftDent when an export is configured or derived from treatment plans.",
    );
    const hygieneRecallWidget = buildContractWidget(
      "hygieneRecall",
      contractCtx,
      practiceConfigured.hygieneRecall ? practiceStatus : "FAILED",
      "Hygiene completed and recall due counts from SoftDent when hygiene_recall_summary export is configured.",
    );
    const operatoryChairs = (practiceDash && practiceDash.operatoryChairs) || [];
    const operatoryConfigured = Array.isArray(operatoryChairs) && operatoryChairs.length > 0;
    const operatoryGridWidget = buildContractWidget(
      "softdentOperatoryGrid",
      contractCtx,
      operatoryConfigured ? practiceStatus : "FAILED",
      "Operatory chair schedule from SoftDent when the dashboard export includes operatory columns.",
    );
    const monthlyRevenue = overviewWidget
      ? overviewWidget.metrics.monthlyRevenue
      : metricValue(qb.revenue);
    const monthlyNetIncome = overviewWidget
      ? overviewWidget.metrics.monthlyNetIncome
      : metricValue(plAmount(qb, "Net Income"));
    const expenseTotal = metricValue(qb.expenses || plAmount(qb, "Expenses"));
    const productionTotal = overviewWidget
      ? overviewWidget.metrics.productionTotal
      : metricValue(sd.production || glanceValue(sd, "Production MTD"));
    const collectionsTotal = overviewWidget
      ? overviewWidget.metrics.collectionsTotal
      : metricValue(sd.collections || glanceValue(sd, "Collections MTD"));
    const accountsReceivableTotal = metricValue(arDash.kpis?.[0]?.value || sd.hero?.value);
    const patientBalanceTotal = metricValue(arDash.kpis?.[0]?.value || sd.hero?.value);
    const arStatus = arDash.kpis ? (arAvailable ? (dashPartial(arDash) ? "DEGRADED" : "SUCCESS") : "DEGRADED") : "FAILED";
    const docsQueueCount = Number(docs.queueCount || (docs.queue && docs.queue.length) || 0);
    const narrativeDraftCount = Number((narratives.drafts && narratives.drafts.length) || narratives.drafts || 0);
    const libraryDocCount = Number(library.results || library.storage?.indexed || (library.docs && library.docs.length) || 0);
    const docsPendingCount = Number(
      (docs.posting || []).find((p) => /pending/i.test(p.label))?.count || 0,
    );
    const docsPeriodReady = Boolean(docs.period && docs.period.label && docs.period.documents);
    const docsDataReady = docsQueueCount > 0 && docsPeriodReady;
    const docsStatus = docsDataReady ? "SUCCESS" : docsQueueCount > 0 ? "DEGRADED" : "FAILED";
    const qbDocImportCount = Number(docs.sourceCounts?.quickbooks || 0);
    const contract = widgetContractApi();
    const missingToken = contract ? contract.MISSING : "—";
    const apDataReady =
      qbStatus === "SUCCESS" ||
      (expenseTotal != null && expenseTotal !== missingToken && expenseTotal !== "—") ||
      qbDocImportCount > 0;
    const narrativeStatus = claims.total > 0 || narrativeDraftCount > 0 ? "SUCCESS" : "FAILED";
    const libraryStatus = libraryDocCount > 0 ? "SUCCESS" : docsQueueCount > 0 ? "DEGRADED" : "FAILED";
    const journalQueue = snap.journalPostingQueue || {};
    const journalItems = Array.isArray(journalQueue.items) ? journalQueue.items : [];
    const journalStatus = journalItems.length > 0 ? "SUCCESS" : docsDataReady ? "DEGRADED" : journalQueue.unavailable ? "DEGRADED" : "FAILED";

    const widgets = {
      practiceFinancialOverview: overviewWidget || {
        key: "practiceFinancialOverview",
        title: "Practice Financial Overview",
        status: collectionHealthDegraded ? "DEGRADED" : mergeWidgetStatus(qbStatus, softdentStatus),
        summary:
          "QuickBooks revenue reflects cash-basis deposits; SoftDent production/collections are operational PMS metrics. Compare collections to QB revenue — not production. Dental A/R is not sourced from QuickBooks.",
        navTarget: WIDGET_NAV.practiceFinancialOverview,
        metricLabels: WIDGET_METRIC_LABELS.practiceFinancialOverview,
        metrics: {
          monthlyRevenue,
          monthlyNetIncome,
          productionTotal,
          collectionsTotal,
        },
      },
      financialProductionTrend: trendWidget || {
        key: "financialProductionTrend",
        title: "Production Trend & YTD",
        status: financialStatus,
        summary:
          "Production trend and trailing collection rate from imported SoftDent months. Incomplete latest months are excluded from the trailing rate.",
        navTarget: WIDGET_NAV.financialProductionTrend,
        metricLabels: WIDGET_METRIC_LABELS.financialProductionTrend,
        metrics: {
          productionMtd: metricValue(fin.productionMtd?.value),
          productionTrendLatest: lastSeriesValue(fin.productionTrend?.production),
          ytdProduction: metricValue((fin.productionTrend?.ytd || []).find((m) => m.label === "YTD Production")?.value),
          trailingCollectionRate: metricValue(
            (fin.productionTrend?.ytd || []).find((m) => m.label === "Trailing Collection Rate")?.value ||
              (fin.productionTrend?.ytd || []).find((m) => m.label === "YTD Collection Rate")?.value,
          ),
        },
      },
      nr2KpiRibbon: {
        key: "nr2KpiRibbon",
        title: "Cross-Analytics KPI Ribbon",
        status: ribbonStatus,
        summary: "Composite KPI tiles from production reconciliation, collection lag, QuickBooks revenue, and SoftDent production trend.",
        navTarget: WIDGET_NAV.nr2KpiRibbon,
        metrics: {
          tileCount: metricValue((analyticsPack.ribbon.tiles || []).length || null),
          latestVariancePct: metricValue(
            analyticsPack.recon.latest && analyticsPack.recon.latest.variancePct != null
              ? `${analyticsPack.recon.latest.variancePct}%`
              : null,
          ),
          collectionLagDays: metricValue(analyticsPack.lag.avgLagDays != null ? `${analyticsPack.lag.avgLagDays} days` : null),
          latestQbRevenue: metricValue(
            analyticsPack.qbRev.values && analyticsPack.qbRev.values.length
              ? `$${Math.round(analyticsPack.qbRev.values[analyticsPack.qbRev.values.length - 1]).toLocaleString()}`
              : null,
          ),
        },
      },
      nr2ProductionReconciliation: {
        key: "nr2ProductionReconciliation",
        title: "Production vs QuickBooks Reconciliation",
        status: reconStatus,
        summary:
          "Monthly SoftDent production compared to QuickBooks revenue (cash-basis deposits). Variance highlights timing and basis differences — not posting errors.",
        navTarget: WIDGET_NAV.nr2ProductionReconciliation,
        metrics: {
          comparablePeriods: metricValue(reconComparable.length || null),
          latestPeriod: metricValue(analyticsPack.recon.latest ? analyticsPack.recon.latest.period : null),
          latestVariancePct: metricValue(
            analyticsPack.recon.latest && analyticsPack.recon.latest.variancePct != null
              ? `${analyticsPack.recon.latest.variancePct}%`
              : null,
          ),
          latestSoftdentProduction: metricValue(
            analyticsPack.recon.latest && analyticsPack.recon.latest.softdentProduction != null
              ? `$${Math.round(analyticsPack.recon.latest.softdentProduction).toLocaleString()}`
              : null,
          ),
          latestQuickbooksRevenue: metricValue(
            analyticsPack.recon.latest && analyticsPack.recon.latest.quickbooksRevenue != null
              ? `$${Math.round(analyticsPack.recon.latest.quickbooksRevenue).toLocaleString()}`
              : null,
          ),
        },
      },
      nr2CollectionLag: {
        key: "nr2CollectionLag",
        title: "Collection Lag (DSO)",
        status: lagStatus,
        summary: analyticsPack.lag.dsoProxy
          ? "Weighted days-sales-outstanding proxy from SoftDent A/R aging buckets."
          : "Collection lag proxy from latest SoftDent production vs collections when A/R aging is unavailable.",
        navTarget: WIDGET_NAV.nr2CollectionLag,
        metrics: {
          avgLagDays: metricValue(analyticsPack.lag.avgLagDays != null ? `${analyticsPack.lag.avgLagDays} days` : null),
          dsoProxy: metricValue(analyticsPack.lag.dsoProxy ? "A/R weighted" : analyticsPack.lag.hasData ? "Monthly proxy" : null),
        },
      },
      nr2GoalScorecard: {
        key: "nr2GoalScorecard",
        title: "Production Goal Scorecard",
        status: analyticsPack.goal.hasData ? (analyticsPack.goal.pctOfGoal != null && analyticsPack.goal.pctOfGoal >= 95 ? "SUCCESS" : "DEGRADED") : "FAILED",
        summary: "YTD SoftDent production compared to operator goal (env NR2_GOAL_PRODUCTION_YTD or 105% of imported YTD).",
        navTarget: WIDGET_NAV.nr2GoalScorecard,
        metrics: {
          ytdProduction: metricValue(
            analyticsPack.goal.ytdProduction != null ? `$${Math.round(analyticsPack.goal.ytdProduction).toLocaleString()}` : null,
          ),
          targetProduction: metricValue(
            analyticsPack.goal.targetProduction != null ? `$${Math.round(analyticsPack.goal.targetProduction).toLocaleString()}` : null,
          ),
          pctOfGoal: metricValue(analyticsPack.goal.pctOfGoal != null ? `${analyticsPack.goal.pctOfGoal}%` : null),
        },
      },
      nr2AlertTicker: {
        key: "nr2AlertTicker",
        title: "Exception Alert Ticker",
        status: analyticsPack.alerts.hasData ? "SUCCESS" : "FAILED",
        summary: "Rolling exception strip from production variance, collection lag, and A/R 90+ bucket thresholds.",
        navTarget: WIDGET_NAV.nr2AlertTicker,
        metrics: {
          alertCount: metricValue((analyticsPack.alerts.items || []).length || null),
          topAlert: metricValue((analyticsPack.alerts.items && analyticsPack.alerts.items[0] && analyticsPack.alerts.items[0].text) || null),
        },
      },
      nr2MonthlyTrendCombo: {
        key: "nr2MonthlyTrendCombo",
        title: "Executive Monthly Trend",
        status: analyticsPack.combo.hasData ? mergeWidgetStatus(financialStatus, qbStatus) : "FAILED",
        summary: "Combined SoftDent production, collections, and QuickBooks revenue by month for executive review.",
        navTarget: WIDGET_NAV.nr2MonthlyTrendCombo,
        metrics: {
          periodCount: metricValue((analyticsPack.combo.labels || []).length || null),
          latestPeriod: metricValue(
            analyticsPack.combo.labels && analyticsPack.combo.labels.length
              ? analyticsPack.combo.labels[analyticsPack.combo.labels.length - 1]
              : null,
          ),
        },
      },
      nr2ProviderCompensationWidget: {
        key: "nr2ProviderCompensationWidget",
        title: "Provider Production Share",
        status: analyticsPack.provComp.hasData ? softdentStatus : "FAILED",
        summary: "Provider production share from SoftDent provider rows or sd_procedures ODBC extract.",
        navTarget: WIDGET_NAV.nr2ProviderCompensationWidget,
        metrics: {
          providerCount: metricValue((analyticsPack.provComp.providers || []).length || null),
          topProvider: metricValue((analyticsPack.provComp.providers && analyticsPack.provComp.providers[0] && analyticsPack.provComp.providers[0].name) || null),
          totalProduction: metricValue(
            analyticsPack.provComp.totalProduction != null ? `$${Math.round(analyticsPack.provComp.totalProduction).toLocaleString()}` : null,
          ),
        },
      },
      softdentProductionDaily: {
        key: "softdentProductionDaily",
        title: "SoftDent Production Trend",
        status: prodDailyStatus,
        summary: "Recent SoftDent production by period from sd_procedures (ODBC extract) or daysheet/dashboard fallback.",
        navTarget: WIDGET_NAV.softdentProductionDaily,
        metrics: {
          granularity: metricValue(analyticsPack.prodDaily.granularity || null),
          pointCount: metricValue((analyticsPack.prodDaily.points || []).length || null),
          latestProduction: metricValue(
            analyticsPack.prodDaily.points && analyticsPack.prodDaily.points.length
              ? `$${Math.round(analyticsPack.prodDaily.points[analyticsPack.prodDaily.points.length - 1].production).toLocaleString()}`
              : null,
          ),
        },
      },
      payerMixAndCollections: payerWidget || {
        key: "payerMixAndCollections",
        title: "Payer Mix & Collections",
        status: financialStatus,
        summary:
          "Payer mix and trailing collection rate from imported SoftDent months. Latest incomplete month is shown separately — do not use it for period close.",
        navTarget: WIDGET_NAV.payerMixAndCollections,
        metricLabels: WIDGET_METRIC_LABELS.payerMixAndCollections,
        metrics: {
          payerMixTotal: metricValue(fin.payerMix?.total),
          collectionRate: metricValue(fin.collectionRateMetrics?.trailingRate || fin.payerMix?.rate),
          latestMonthCollectionRate: metricValue(
            fin.collectionRateMetrics?.latestMonthRate
              ? `${fin.collectionRateMetrics.latestMonthRate}${fin.collectionRateMetrics.latestMonthIncomplete ? " (incomplete)" : ""}`
              : null,
          ),
          trailingCollectionPeriods: metricValue(fin.collectionRateMetrics?.trailingPeriods),
          topPayer: metricValue(firstItem(fin.payerMix?.slices)?.label),
          topPayerShare: metricValue(firstItem(fin.payerMix?.slices)?.pct != null ? `${firstItem(fin.payerMix?.slices).pct}%` : null),
        },
      },
      providerPerformance: providerWidget || {
        key: "providerPerformance",
        title: "Provider Performance",
        status: financialStatus,
        summary: "Provider production split from the owner financial dashboard.",
        navTarget: WIDGET_NAV.providerPerformance,
        metrics: {
          providerCount: metricValue((fin.providers?.rows || []).length || null),
          topProvider: metricValue(firstItem(fin.providers?.rows)?.name),
          topProviderProduction: metricValue(firstItem(fin.providers?.rows)?.amount),
          providerTotal: metricValue(fin.providers?.total?.amount),
        },
      },
      ebitdaNormalization: {
        key: "ebitdaNormalization",
        title: "EBITDA Normalization",
        status: mergeWidgetStatus(qbStatus, financialQualityStatus),
        summary:
          "Potential EBITDA add-backs and expense-category totals from the financial and QuickBooks import cache. Compare category pivot scope to monthly P&L expenses.",
        navTarget: WIDGET_NAV.ebitdaNormalization,
        metricLabels: WIDGET_METRIC_LABELS.ebitdaNormalization,
        metrics: {
          ebitdaAddBackTotal: metricValue(qb.ebitdaTotal),
          ebitdaCandidateCount: metricValue((qb.ebitdaCandidates || []).length || null),
          expenseCategoriesTotal: metricValue(qb.expenseCategories?.total),
          expenseCategoriesScope: metricValue(qb.expenseCategories?.scopeLabel),
          monthlyExpensesLatest: metricValue(qb.expenseCategories?.monthlyExpensesLatest || qb.expenses),
        },
      },
      quickbooksProfitLossDetail: {
        key: "quickbooksProfitLossDetail",
        title: "QuickBooks P&L Detail",
        status: qbStatus,
        summary: "Revenue, gross profit, COGS, operating expenses, and margin detail from the read-only QuickBooks P&L cache.",
        navTarget: WIDGET_NAV.quickbooksProfitLossDetail,
        metrics: {
          revenue: rowAmount(qb.pl?.rows, "Revenue"),
          cogs: rowAmount(qb.pl?.rows, "Cost of Goods Sold"),
          grossProfit: rowAmount(qb.pl?.rows, "Gross Profit"),
          operatingExpenses: rowAmount(qb.pl?.rows, "Operating Expenses"),
          netIncome: rowAmount(qb.pl?.rows, "Net Income"),
        },
      },
      quickbooksMonthlyRevenue: {
        key: "quickbooksMonthlyRevenue",
        title: "Monthly Revenue Trend",
        status: qbRevStatus,
        summary: "QuickBooks monthly TotalIncome from the read-only P&L/revenue import cache (cash-basis deposits).",
        navTarget: WIDGET_NAV.quickbooksMonthlyRevenue,
        metrics: {
          monthCount: metricValue((analyticsPack.qbRev.labels || []).length || null),
          latestMonth: metricValue(
            analyticsPack.qbRev.labels && analyticsPack.qbRev.labels.length
              ? analyticsPack.qbRev.labels[analyticsPack.qbRev.labels.length - 1]
              : null,
          ),
          latestRevenue: metricValue(
            analyticsPack.qbRev.values && analyticsPack.qbRev.values.length
              ? `$${Math.round(analyticsPack.qbRev.values[analyticsPack.qbRev.values.length - 1]).toLocaleString()}`
              : null,
          ),
        },
      },
      quickbooksNetIncomeSummary: {
        key: "quickbooksNetIncomeSummary",
        title: "Net Income Summary",
        status: qbReportsPack.netIncome.hasData ? qbStatus : qbStatus === "SUCCESS" ? "DEGRADED" : "FAILED",
        summary: "YTD and latest-month net income from QuickBooks monthly P&L import rows.",
        navTarget: WIDGET_NAV.quickbooksNetIncomeSummary,
        metrics: {
          ytdNetIncome: metricValue(
            qbReportsPack.netIncome.ytdNetIncome != null ? `$${Math.round(qbReportsPack.netIncome.ytdNetIncome).toLocaleString()}` : null,
          ),
          latestMonth: metricValue(qbReportsPack.netIncome.latestMonth),
          latestNetIncome: metricValue(
            qbReportsPack.netIncome.latestNetIncome != null ? `$${Math.round(qbReportsPack.netIncome.latestNetIncome).toLocaleString()}` : null,
          ),
        },
      },
      quickbooksBalanceSheetSummary: {
        key: "quickbooksBalanceSheetSummary",
        title: "Balance Sheet Summary",
        status: qbReportsPack.balanceSheet.hasData ? qbStatus : "DEGRADED",
        summary: "Asset and equity proxy from QuickBooks A/R plus P&L import cache.",
        navTarget: WIDGET_NAV.quickbooksBalanceSheetSummary,
        metrics: {
          assetLines: metricValue((qbReportsPack.balanceSheet.assets || []).length || null),
          equity: metricValue(
            qbReportsPack.balanceSheet.equity != null ? `$${Math.round(qbReportsPack.balanceSheet.equity).toLocaleString()}` : null,
          ),
        },
      },
      quickbooksCashFlowTrend: {
        key: "quickbooksCashFlowTrend",
        title: "Cash Flow Trend",
        status: qbReportsPack.cashFlow.hasData ? qbStatus : "DEGRADED",
        summary: "Monthly net cash flow proxy from QuickBooks P&L income minus expenses.",
        navTarget: WIDGET_NAV.quickbooksCashFlowTrend,
        metrics: {
          monthCount: metricValue((qbReportsPack.cashFlow.labels || []).length || null),
          latestNet: metricValue(
            qbReportsPack.cashFlow.net && qbReportsPack.cashFlow.net.length
              ? `$${Math.round(qbReportsPack.cashFlow.net[qbReportsPack.cashFlow.net.length - 1]).toLocaleString()}`
              : null,
          ),
        },
      },
      quickbooksRevenueByService: {
        key: "quickbooksRevenueByService",
        title: "Revenue by Service",
        status: qbReportsPack.revenueSvc.hasData ? qbStatus : "DEGRADED",
        summary: "Category/service revenue slices from QuickBooks expense categories or P&L proxy.",
        navTarget: WIDGET_NAV.quickbooksRevenueByService,
        metrics: {
          sliceCount: metricValue((qbReportsPack.revenueSvc.slices || []).length || null),
          topService: metricValue(firstItem(qbReportsPack.revenueSvc.slices)?.label),
        },
      },
      quickbooksArAging: {
        key: "quickbooksArAging",
        title: "QuickBooks A/R Aging",
        status: qbReportsPack.arAging.hasData ? qbStatus : "DEGRADED",
        summary: "QuickBooks A/R aging buckets from import cache (informational cross-check vs SoftDent A/R).",
        navTarget: WIDGET_NAV.quickbooksArAging,
        metrics: {
          bucketCount: metricValue((qbReportsPack.arAging.buckets || []).length || null),
          totalAr: metricValue(
            qbReportsPack.arAging.total != null ? `$${Math.round(qbReportsPack.arAging.total).toLocaleString()}` : null,
          ),
        },
      },
      quickbooksExpenseBreakdown: {
        key: "quickbooksExpenseBreakdown",
        title: "Operating Expenses",
        status:
          qb.expenseCategories?.slices?.length || qb.monthlyExpenses?.values?.length ? qbStatus : "FAILED",
        summary: "Monthly expense trend and category breakdown from the QuickBooks import cache.",
        navTarget: WIDGET_NAV.quickbooksExpenseBreakdown,
        metrics: {
          expenseCategoriesTotal: metricValue(qb.expenseCategories?.total),
          expenseCategoriesScope: metricValue(qb.expenseCategories?.scopeLabel),
          monthlyExpensesLatest: metricValue(qb.expenseCategories?.monthlyExpensesLatest || qb.expenses),
          topCategory: metricValue(firstItem(qb.expenseCategories?.slices)?.label),
          topCategoryShare: metricValue(
            firstItem(qb.expenseCategories?.slices)?.pct != null ? `${firstItem(qb.expenseCategories?.slices).pct}%` : null,
          ),
        },
      },
      accountsPayableAutomation: {
        key: "accountsPayableAutomation",
        // Reflects both QuickBooks expenses and the local document queue. When
        // documents exist but QuickBooks data is missing, show partial rather
        // than a false "No data yet".
        status: apDataReady ? "SUCCESS" : docsQueueCount > 0 ? "DEGRADED" : qbStatus,
        title: "Accounts Payable Automation",
        summary: "QuickBooks expense totals and local document review-queue counts from the import cache.",
        navTarget: WIDGET_NAV.accountsPayableAutomation,
        metrics: {
          expenseTotal,
          postingQueuePendingCount: pendingPosting || null,
        },
      },
      documentIntakeQueue: {
        key: "documentIntakeQueue",
        title: "Document Intake Queue",
        status: docsStatus,
        summary: "Financial summary queue from SoftDent and QuickBooks import cache (monthly totals, A/R aging, production/collections). Individual invoices are not imported.",
        navTarget: WIDGET_NAV.documentIntakeQueue,
        metrics: {
          queueCount: metricValue(docs.queueCount),
          pendingReviewCount: metricValue((docs.posting || []).find((p) => /pending/i.test(p.label))?.count),
          readyToPostCount: metricValue((docs.posting || []).find((p) => /ready/i.test(p.label))?.count),
          quickbooksImportCount: metricValue(docs.sourceCounts?.quickbooks),
          softdentImportCount: metricValue(docs.sourceCounts?.softdent),
          ocrImportCount: metricValue(docs.sourceCounts?.ocr),
          oldestVisibleAgeDays: metricValue(Math.max.apply(null, (docs.top || []).map((d) => Number(d.age) || 0)) || null),
        },
      },
      documentPreview: {
        key: "documentPreview",
        title: "Selected Document Preview",
        status: docsStatus,
        summary: "Current selected or first visible accounting document preview metadata. Review only; HAL reads QuickBooks only.",
        navTarget: WIDGET_NAV.documentPreview,
        metrics: {
          selectedDocumentId: metricValue(firstItem(docs.top)?.id),
          vendor: metricValue(firstItem(docs.top)?.vendor),
          amount: metricValue(firstItem(docs.top)?.amount),
          status: metricValue(firstItem(docs.top)?.status),
        },
      },
      periodCloseAndPosting: {
        key: "periodCloseAndPosting",
        title: "Period Close & Posting",
        status: docsStatus,
        summary: "Accounting period close posture and document posting progress from the documents workbench cache.",
        navTarget: WIDGET_NAV.periodCloseAndPosting,
        metrics: {
          periodLabel: metricValue(docs.period?.label),
          documentsInPeriod: metricValue(docs.period?.documents),
          postedPct: metricValue(docs.period?.postedPct != null ? `${docs.period.postedPct}%` : null),
          pendingAmount: metricValue(docs.period?.pendingAmount || docs.period?.pending),
        },
      },
      journalPostingQueue: {
        key: "journalPostingQueue",
        title: "Journal Posting Queue",
        status: journalStatus,
        summary: "Local SQLite journal posting queue for reviewed accruals. Requires NR2 server on loopback (Start Program).",
        navTarget: WIDGET_NAV.journalPostingQueue,
        metrics: {
          queueCount: metricValue(journalItems.length || journalQueue.metrics?.pending || null),
          pendingReview: metricValue(journalQueue.metrics?.pending),
          readyToExport: metricValue(journalQueue.metrics?.ready),
        },
      },
      smartClaimsAndReceivables: {
        key: "smartClaimsAndReceivables",
        title: "Smart Claims & Receivables",
        status: claimsStatus,
        summary: arAvailable
          ? "SoftDent claims and receivables totals derived from local practice operations data."
          : "SoftDent claims totals from local data; dental A/R is unavailable until an explicit SoftDent A/R export is present.",
        navTarget: WIDGET_NAV.smartClaimsAndReceivables,
        metrics: {
          outstandingClaimCount: claims.total || null,
          accountsReceivableTotal,
        },
      },
      claimsPipeline: {
        key: "claimsPipeline",
        title: "Claims Pipeline",
        status: claimsSnap.total > 0 ? "SUCCESS" : "FAILED",
        summary: "Claim lifecycle lane counts from the local claims workbench. Payer submission remains locked.",
        navTarget: WIDGET_NAV.claimsPipeline,
        metrics: {
          totalClaims: metricValue(claimsSnap.total),
          draftCount: metricValue(claimsSnap.byStatus?.Draft || claimsSnap.laneTotals?.Draft),
          needsReviewCount: metricValue(claimsSnap.byStatus?.["Needs Review"] || claimsSnap.laneTotals?.["Needs Review"]),
          readyCount: metricValue(claimsSnap.byStatus?.Ready || claimsSnap.laneTotals?.Ready),
          deniedCount: metricValue(claimsSnap.byStatus?.Denied || claimsSnap.laneTotals?.Denied),
        },
      },
      arAgingAndCollections: {
        key: "arAgingAndCollections",
        title: "A/R Aging & Collections",
        status:
          fin.arCrossCheck && fin.arCrossCheck.comparable && fin.arCrossCheck.withinTolerance === false
            ? "DEGRADED"
            : arStatus,
        summary: arAvailable
          ? "A/R aging buckets, collections trend, and follow-up queue counts from the A/R dashboard cache. Cross-check SoftDent A/R against QuickBooks balance-sheet A/R when both exports exist."
          : "A/R dashboard cache is present but verified dental A/R totals are unavailable until an explicit SoftDent A/R export is present.",
        navTarget: WIDGET_NAV.arAgingAndCollections,
        metricLabels: WIDGET_METRIC_LABELS.arAgingAndCollections,
        metrics: {
          totalOutstanding: metricValue(kpiValue(arDash.kpis, "Total Outstanding")),
          quickbooksArTotal: metricValue(
            fin.arCrossCheck && fin.arCrossCheck.quickbooksTotal != null
              ? `$${Number(fin.arCrossCheck.quickbooksTotal).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
              : null,
          ),
          arCrossSourceVariance: metricValue(
            fin.arCrossCheck && fin.arCrossCheck.variance != null && fin.arCrossCheck.quickbooksTotal != null
              ? `$${Number(fin.arCrossCheck.variance).toFixed(2)} (informational)`
              : null,
          ),
          aging90PlusPct: metricValue(kpiValue(arDash.kpis, "90+ Days %")),
          collectionsThisPeriod: metricValue(kpiValue(arDash.kpis, "Collections This 30 Days")),
          followUpQueueCount: sumCounts(arDash.followUp),
        },
      },
      arOutstandingClaims: {
        key: "arOutstandingClaims",
        title: "Top Outstanding Claims",
        status: arStatus,
        summary: arAvailable
          ? "Top outstanding claims list and oldest claim age from the A/R dashboard cache."
          : "Top claims list is available, but verified dental A/R totals stay hidden until an explicit SoftDent A/R export is present.",
        navTarget: WIDGET_NAV.arOutstandingClaims,
        metrics: {
          topClaimCount: metricValue((arDash.topClaims || []).length || null),
          topClaimId: metricValue(firstItem(arDash.topClaims)?.claim),
          topClaimOutstanding: metricValue(firstItem(arDash.topClaims)?.outstanding),
          oldestClaimDays: metricValue(Math.max.apply(null, (arDash.topClaims || []).map((c) => Number(c.days) || 0)) || null),
        },
      },
      careDeliveryPerformance: {
        key: "careDeliveryPerformance",
        title: "Care Delivery Performance",
        status: careStatus,
        summary: arAvailable
          ? "Practice-wide SoftDent operational balances from the import cache."
          : "Practice-wide SoftDent operational activity from the import cache; patient A/R balances are unavailable until an explicit SoftDent A/R export is present.",
        navTarget: WIDGET_NAV.careDeliveryPerformance,
        metrics: {
          patientBalanceTotal,
          providerCount: metricValue((fin.providers?.rows || []).length || null),
          patientCount: metricValue(glanceValue(sd, "Total Patients")),
        },
      },
      softdentArAging: {
        key: "softdentArAging",
        title: "SoftDent A/R Aging",
        status: arAvailable ? softdentStatus : "DEGRADED",
        summary: arAvailable
          ? "SoftDent daysheet A/R aging buckets from the local import cache."
          : "SoftDent aging buckets are withheld from HAL until a verified A/R export is present.",
        navTarget: WIDGET_NAV.softdentArAging,
        metrics: {
          totalAr: metricValue(sd.hero?.value),
          currentBucket: metricValue((sd.aging || []).find((a) => /0-30|current/i.test(a.bucket || ""))?.amount),
          ninetyPlusBucket: metricValue((sd.aging || []).find((a) => /^\s*(90\+|90\s*\+|120)/i.test(a.bucket || ""))?.amount),
          bucketCount: metricValue((sd.aging || []).length || null),
        },
      },
      softdentResponsibility: {
        key: "softdentResponsibility",
        title: "Insurance vs Patient Responsibility",
        status: arAvailable ? softdentStatus : "DEGRADED",
        summary: arAvailable
          ? "Insurance/patient A/R split and collectability from the SoftDent dashboard cache."
          : "Responsibility split is withheld until a verified SoftDent A/R export is present.",
        navTarget: WIDGET_NAV.softdentResponsibility,
        metrics: {
          insuranceAmount: metricValue(sd.responsibility?.insurance?.amount),
          patientAmount: metricValue(sd.responsibility?.patient?.amount),
          collectability: metricValue(sd.responsibility?.collectability),
          collectableAmount: metricValue(sd.responsibility?.collectable),
        },
      },
      newPatients: newPatientsWidget || {
        key: "newPatients",
        title: "New Patients",
        status: "FAILED",
        summary: "New patient counts from SoftDent when the export is configured. Until then, HAL reports Not Configured.",
        navTarget: WIDGET_NAV.newPatients,
        metrics: {
          newPatientCount: "Not Configured",
          period: "Not Configured",
        },
      },
      treatmentPlanSummary: treatmentWidget || {
        key: "treatmentPlanSummary",
        title: "Treatment Plan Summary",
        status: "FAILED",
        summary: "Treatment plan presented/accepted summary from SoftDent when the export is configured.",
        navTarget: WIDGET_NAV.treatmentPlanSummary,
        metrics: {
          plansPresented: "Not Configured",
          plansAccepted: "Not Configured",
          presentedValue: "Not Configured",
        },
      },
      caseAcceptance: caseAcceptanceWidget || {
        key: "caseAcceptance",
        title: "Case Acceptance",
        status: "FAILED",
        summary: "Case acceptance rate from SoftDent when the export is configured or derived from treatment plans.",
        navTarget: WIDGET_NAV.caseAcceptance,
        metrics: {
          acceptanceRate: "Not Configured",
          acceptedCount: "Not Configured",
          presentedCount: "Not Configured",
        },
      },
      hygieneRecall: hygieneRecallWidget || {
        key: "hygieneRecall",
        title: "Hygiene & Recall",
        status: "FAILED",
        summary: "Hygiene completed and recall due from SoftDent when hygiene_recall_summary export is configured.",
        navTarget: WIDGET_NAV.hygieneRecall,
        metrics: {
          hygieneCompleted: "Not Configured",
          recallDue: "Not Configured",
          period: "Not Configured",
        },
      },
      softdentOperatoryGrid: operatoryGridWidget || {
        key: "softdentOperatoryGrid",
        title: "Operatory Schedule",
        status: "FAILED",
        summary: "Operatory chair schedule from SoftDent when the dashboard export includes operatory columns.",
        navTarget: WIDGET_NAV.softdentOperatoryGrid,
        metrics: {
          chairCount: "Not Configured",
          activeChairs: "Not Configured",
          nextOpenSlot: "Not Configured",
        },
      },
      softdentCollectionsDaily: {
        key: "softdentCollectionsDaily",
        title: "Collections Trend",
        status: sdDailyPack.collections.hasData ? softdentStatus : softdentStatus === "SUCCESS" ? "DEGRADED" : "FAILED",
        summary: "Daily or monthly collections from sd_payments ODBC extract or SoftDent dashboard rows.",
        navTarget: WIDGET_NAV.softdentCollectionsDaily,
        metrics: {
          pointCount: metricValue((sdDailyPack.collections.labels || sdDailyPack.collections.points || []).length || null),
          latestCollections: metricValue(
            sdDailyPack.collections.values && sdDailyPack.collections.values.length
              ? `$${Math.round(sdDailyPack.collections.values[sdDailyPack.collections.values.length - 1]).toLocaleString()}`
              : null,
          ),
        },
      },
      softdentNewPatientsMTD: {
        key: "softdentNewPatientsMTD",
        title: "New Patients (MTD)",
        status: sdDailyPack.newPatients.hasData ? practiceStatus : "DEGRADED",
        summary: "New patient count for the current month from sd_patients or practice export.",
        navTarget: WIDGET_NAV.softdentNewPatientsMTD,
        metrics: {
          count: metricValue(sdDailyPack.newPatients.count),
          period: metricValue(sdDailyPack.newPatients.period),
        },
      },
      softdentClaimsOutstanding: {
        key: "softdentClaimsOutstanding",
        title: "Outstanding Claims",
        status: sdDailyPack.claims.hasData ? claimsStatus : "DEGRADED",
        summary: "Top outstanding claims from sd_claims or SoftDent claims export.",
        navTarget: WIDGET_NAV.softdentClaimsOutstanding,
        metrics: {
          claimCount: metricValue((sdDailyPack.claims.claims || []).length || null),
          totalOutstanding: metricValue(
            sdDailyPack.claims.totalOutstanding != null
              ? `$${Math.round(sdDailyPack.claims.totalOutstanding).toLocaleString()}`
              : null,
          ),
        },
      },
      softdentProviderProduction: {
        key: "softdentProviderProduction",
        title: "Provider Production (Daily)",
        status: sdDailyPack.providers.hasData ? financialStatus : "DEGRADED",
        summary: "Provider production totals from sd_procedures or financial dashboard provider split.",
        navTarget: WIDGET_NAV.softdentProviderProduction,
        metrics: {
          providerCount: metricValue((sdDailyPack.providers.providers || []).length || null),
          topProvider: metricValue(firstItem(sdDailyPack.providers.providers)?.providerCode),
          totalProduction: metricValue(
            sdDailyPack.providers.total != null ? `$${Math.round(sdDailyPack.providers.total).toLocaleString()}` : null,
          ),
        },
      },
      softdentAppointmentsSnapshot: {
        key: "softdentAppointmentsSnapshot",
        title: "Appointments Snapshot",
        status: sdDailyPack.appointments.hasData ? practiceStatus : "DEGRADED",
        summary: "Recent appointments from sd_appointments or operatory chair schedule.",
        navTarget: WIDGET_NAV.softdentAppointmentsSnapshot,
        metrics: {
          appointmentCount: metricValue((sdDailyPack.appointments.appointments || []).length || null),
        },
      },
      narrativeWorkflow: {
        key: "narrativeWorkflow",
        title: "Insurance Narrative Workflow",
        status: narrativeStatus,
        summary: "Insurance narrative composer, draft count, latest draft, and focus mode. Draft only; no payer submission.",
        navTarget: WIDGET_NAV.narrativeWorkflow,
        metrics: {
          draftCount: metricValue(narratives.drafts),
          latestDraft: metricValue(narratives.latest?.version),
          focus: metricValue(narratives.focus),
          modifiedBy: metricValue(narratives.latest?.by),
        },
      },
      documentLibrary: {
        key: "documentLibrary",
        title: "Document Library",
        status: libraryStatus,
        summary: "Indexed document library volume, storage posture, and most recent visible document from the local library cache.",
        navTarget: WIDGET_NAV.documentLibrary,
        metrics: {
          indexedDocuments: metricValue(library.storage?.indexed || library.results),
          storageUsedPct: metricValue(library.storage?.usedPct != null ? `${library.storage.usedPct}%` : null),
          storageCapacity: metricValue(library.storage?.capacity),
          topDocument: metricValue(firstItem(library.top)?.title),
        },
      },
      halImportHealth: buildImportHealthWidget(snap.importBundle),
      halMorningBriefing: {
        key: "halMorningBriefing",
        title: "Morning Briefing",
        status: snap.halMorningBriefing || (snap.halProactiveBriefing && snap.halProactiveBriefing.morningBriefing) ? "SUCCESS" : "DEGRADED",
        summary: "Cross-domain synthesis with KPI ribbon and consent-gated actuators.",
        navTarget: "hal",
        metrics: {},
      },
      halSituationalHero: {
        key: "halSituationalHero",
        title: "Situational Hero",
        status: "SUCCESS",
        summary: "Living command posture with alert ticker and quick HAL prompts.",
        navTarget: "hal",
        metrics: {},
      },
      halAskHal: {
        key: "halAskHal",
        title: "Ask HAL",
        status: "SUCCESS",
        summary: "HAL command center — ask questions, explain widgets, and jump to staff work surfaces.",
        navTarget: "hal",
        metrics: {
          registeredWidgets: metricValue(WIDGET_ORDER.length),
        },
      },
      sidenotesProgram: {
        key: "sidenotesProgram",
        title: "Staff Notes",
        status: (() => {
          const inbox = snap.sidenotesInbox;
          const sideNotes = snap.sideNotes || {};
          const activeLocal = Number(sideNotes.activeCount || sideNotes.total || 0);
          if (inbox && inbox.monitor) {
            const stations = inbox.monitor.stations;
            if (Array.isArray(stations) && stations.some((s) => s && s.live)) return "SUCCESS";
            return "DEGRADED";
          }
          if (snap.sidenotesHubPath) return "DEGRADED";
          if (activeLocal > 0) return "SUCCESS";
          return "DEGRADED";
        })(),
        summary:
          snap.sidenotesInbox && snap.sidenotesInbox.monitor
            ? "SideNotesIM workstation routing — HAL announces sender metadata only; message text is never read aloud."
            : "Local HAL staff scratch notes on this device. Office messaging uses NR2 Workstation, not SideNotesIM.",
        navTarget: "hal",
        metrics: {
          watchersOnline: metricValue(
            snap.sidenotesInbox && snap.sidenotesInbox.monitor && snap.sidenotesInbox.monitor.stations
              ? snap.sidenotesInbox.monitor.stations.filter((s) => s.live).length
              : snap.sidenotesHubPath
                ? 1
                : snap.sideNotes && snap.sideNotes.activeCount != null
                  ? snap.sideNotes.activeCount
                  : null,
          ),
        },
      },
    };

    const feed = {
      meta: skillMeta("widgets.feed", "programSnapshot"),
      manager: "Import cache",
      runId: uid("run"),
      generatedAt: snap.gatheredAt || new Date().toISOString(),
      widgets,
      importMode: (snap.importBundle && snap.importBundle.importMode) || "document-inbox-cache",
      sources: {
        quickbooks: { lastStatus: qbStatus, origin: "local" },
        softdent: { lastStatus: softdentStatus, origin: "local" },
      },
      jobs: {},
      localOnly: true,
    };
    // Live source freshness/status for the Source Intake panel — driven by the
    // actual import bundle so the panel never reports a stale hardcoded state.
    const hasData = (dash) => Boolean(dash && (dash.dataSource === "import" || dash.dataSource === "persisted"));
    const sdFreshness =
      (sd.health || []).find((h) => /freshness/i.test(String(h.label || "")))?.value ||
      firstItem(sd.exports)?.completed ||
      (hasData(sd) ? sd.date : null);
    const bundle = snap.importBundle || null;
    const softdentImportHealth = systemImportHealth(bundle, "softdent");
    const quickbooksImportHealth = systemImportHealth(bundle, "quickbooks");
    feed.sourceHealth = {
      softdent: {
        status: softdentStatus,
        hasData: hasData(sd),
        connectionStatus: softdentImportHealth.connectionStatus,
        datasetSummary: softdentImportHealth.datasetSummary,
        datasetLines: softdentImportHealth.datasetLines,
        detail: softdentImportHealth.detail,
        freshness: hasData(sd) ? sdFreshness || "Imported" : null,
        syncState: hasData(sd) ? "Imported · read-only" : null,
      },
      quickbooks: {
        status: qbStatus,
        hasData: hasData(qb),
        connectionStatus: quickbooksImportHealth.connectionStatus,
        datasetSummary: quickbooksImportHealth.datasetSummary,
        datasetLines: quickbooksImportHealth.datasetLines,
        detail: quickbooksImportHealth.detail,
        freshness: hasData(qb) ? qb.lastSync || qb.sync?.lastSync || "Imported" : null,
        syncState: hasData(qb) ? qb.syncStatus || qb.sync?.status || "Connected" : null,
      },
      documents: {
        status: docsStatus,
        hasData: docsQueueCount > 0,
        freshness: docsQueueCount > 0 ? "Queue loaded" : null,
        syncState: docsQueueCount > 0 ? "Local review" : null,
      },
      library: {
        status: libraryStatus,
        hasData: libraryDocCount > 0,
        freshness: libraryDocCount > 0 ? "Index current" : null,
        syncState: libraryDocCount > 0 ? "Read-only" : null,
      },
    };

    // Live per-surface state for the Staff Work Surfaces panel (was hardcoded
    // "Not available" / "—"). Keyed by the page target each surface opens.
    feed.surfaceCounts = {
      financial: {
        status: financialStatus,
        updated: financialStatus === "SUCCESS" ? metricValue(fin.footer?.refreshed) || "Imported" : null,
        items: (fin.providers?.rows || []).length || null,
        itemsLabel: "providers",
      },
      claims: {
        status: claimsSnap.total > 0 ? "SUCCESS" : "FAILED",
        updated: claimsSnap.total > 0 ? "Imported" : null,
        items: claimsSnap.total || null,
        itemsLabel: "claims",
      },
      narratives: {
        status: narrativeStatus,
        updated: narratives.drafts ? "Draft saved" : null,
        items: narratives.drafts || null,
        itemsLabel: "drafts",
      },
      documents: {
        status: docsStatus,
        updated: docsStatus === "SUCCESS" ? "Queue loaded" : null,
        items: docs.queueCount || null,
        itemsLabel: "in queue",
      },
      ar: {
        status: arStatus,
        updated: arAvailable ? "Imported" : null,
        items: (arDash.aging || arDash.buckets || []).length || null,
        itemsLabel: "aging buckets",
      },
      library: {
        status: libraryStatus,
        updated: libraryDocCount > 0 ? "Index current" : null,
        items: libraryDocCount || null,
        itemsLabel: "documents",
      },
      softdent: {
        status: softdentStatus,
        updated: softdentStatus !== "FAILED" ? metricValue(fin.footer?.refreshed) || "Imported" : null,
        items: (sd.providers?.rows || fin.providers?.rows || []).length || null,
        itemsLabel: "providers",
      },
      quickbooks: {
        status: qbStatus,
        updated: qbStatus !== "FAILED" ? qb.lastSync || "Imported" : null,
        items: (qb.pl && qb.pl.rows && qb.pl.rows.length) || null,
        itemsLabel: "P&L rows",
      },
      "office-manager": {
        status:
          snap.officeTasks && snap.officeTasks.length
            ? "SUCCESS"
            : snap.officeTasksState === "not_configured"
              ? claimsSnap.total > 0
                ? "DEGRADED"
                : "FAILED"
              : "DEGRADED",
        updated: snap.officeTasks && snap.officeTasks.length ? "Local tasks loaded" : null,
        items: (snap.officeTasks && snap.officeTasks.length) || null,
        itemsLabel: "tasks",
      },
    };

    const officeAttention = Object.values(feed.widgets || {}).filter((widget) => {
      const status = String(widget && widget.status || "").toUpperCase();
      return status === "FAILED" || status === "DEGRADED";
    });
    feed.officeWidgets = {
      officeManagerPriorities: {
        key: "officeManagerPriorities",
        title: "HAL Priorities",
        status: officeAttention.length > 0 ? "DEGRADED" : "SUCCESS",
        summary: officeAttention.length
          ? "HAL is tracking widgets that need data or review and grouping them for office-manager attention."
          : "HAL is monitoring the program with no urgent widget priorities in this snapshot.",
        navTarget: "office-manager",
        metrics: {
          attentionItems: officeAttention.length || 0,
          failedWidgets: officeAttention.filter((w) => String(w.status).toUpperCase() === "FAILED").length,
          partialWidgets: officeAttention.filter((w) => String(w.status).toUpperCase() === "DEGRADED").length,
        },
      },
      officeManagerSurfaces: {
        key: "officeManagerSurfaces",
        title: "Work Surfaces",
        status: "SUCCESS",
        summary: "Office Manager work-surface links route staff to the local pages HAL monitors.",
        navTarget: "office-manager",
        metrics: {
          surfaces: Object.keys(feed.surfaceCounts || {}).length,
          localOnly: "Yes",
        },
      },
    };

    applyAccountingExcelCommitValidation(feed, snap);
    const publish = publishJobStatus(feed.widgets);
    feed.jobs = {
      importCacheRefresh: { status: publish },
      widgetPublish: {
        status: publish,
        validation: feed.accountingExcelValidation ? feed.accountingExcelValidation.status : "PASS",
      },
    };
    return enforceReceivablesArPolicy(feed, arAvailable);
  }

  // Never present an A/R total when no verified A/R source exists; degrade instead.
  function enforceReceivablesArPolicy(feed, arAvailable) {
    if (arAvailable) return feed;
    [
      ["smartClaimsAndReceivables", ["accountsReceivableTotal"]],
      ["careDeliveryPerformance", ["patientBalanceTotal"]],
      ["arAgingAndCollections", ["totalOutstanding", "aging90PlusPct", "collectionsThisPeriod"]],
      ["arOutstandingClaims", ["topClaimOutstanding"]],
      ["softdentArAging", ["totalAr", "currentBucket", "ninetyPlusBucket"]],
      ["softdentResponsibility", ["insuranceAmount", "patientAmount", "collectability", "collectableAmount"]],
    ].forEach(([key, metricKeys]) => {
      const widget = feed.widgets[key];
      if (!widget || !widget.metrics) return;
      metricKeys.forEach((m) => {
        widget.metrics[m] = null;
      });
      if (String(widget.status).toUpperCase() === "SUCCESS") widget.status = "DEGRADED";
    });
    const publish = publishJobStatus(feed.widgets);
    feed.jobs.importCacheRefresh = Object.assign({}, feed.jobs.importCacheRefresh, { status: publish });
    feed.jobs.widgetPublish = Object.assign({}, feed.jobs.widgetPublish, { status: publish });
    return feed;
  }

  function formatWidgetMetricLabel(key, widgetKey) {
    const scoped = widgetKey && WIDGET_METRIC_LABELS[widgetKey] && WIDGET_METRIC_LABELS[widgetKey][key];
    if (scoped) return scoped;
    return String(key || "")
      .replace(/([A-Z])/g, " $1")
      .replace(/^./, (c) => c.toUpperCase())
      .trim();
  }

  const WIDGET_METRIC_LABELS = {
    practiceFinancialOverview: {
      monthlyRevenue: "QB Revenue (cash basis)",
      monthlyNetIncome: "QB Net Income",
      productionTotal: "SoftDent Production (operational)",
      collectionsTotal: "SoftDent Collections",
    },
    ebitdaNormalization: {
      ebitdaAddBackTotal: "EBITDA Add-Back Total",
      ebitdaCandidateCount: "EBITDA Candidate Count",
      expenseCategoriesTotal: "Expense Categories Total",
      expenseCategoriesScope: "Category Pivot Scope",
      monthlyExpensesLatest: "Monthly Expenses (P&L)",
    },
    arAgingAndCollections: {
      totalOutstanding: "SoftDent A/R Total",
      quickbooksArTotal: "QuickBooks A/R Total",
      arCrossSourceVariance: "A/R Cross-Source Variance",
      aging90PlusPct: "90+ Days %",
      collectionsThisPeriod: "Collections This Period",
      followUpQueueCount: "Follow-Up Queue Count",
    },
    payerMixAndCollections: {
      payerMixTotal: "Payer Mix Total",
      collectionRate: "Trailing Collection Rate (imported months)",
      latestMonthCollectionRate: "Latest Month Collection Rate",
      trailingCollectionPeriods: "Trailing Periods",
      topPayer: "Top Payer",
      topPayerShare: "Top Payer Share",
    },
    financialProductionTrend: {
      productionMtd: "Production MTD",
      productionTrendLatest: "Production Trend Latest",
      ytdProduction: "YTD Production",
      ytdCollectionRate: "Trailing Collection Rate",
      trailingCollectionRate: "Trailing Collection Rate",
    },
  };

  function formatWidgetMetrics(widget) {
    const metrics = (widget && widget.metrics) || {};
    const widgetKey = widget && widget.key;
    const pairs = Object.entries(metrics)
      .filter(([, v]) => v !== null && v !== undefined && v !== "")
      .map(([k, v]) => `${formatWidgetMetricLabel(k, widgetKey)}: ${v}`);
    return pairs.length ? pairs.join(" · ") : "No verified metrics in this snapshot.";
  }

  function widgetMissingMetrics(widget) {
    return Object.entries((widget && widget.metrics) || {})
      .filter(([, value]) => value === null || value === undefined || value === "" || value === "—")
      .map(([key]) => formatWidgetMetricLabel(key, widget && widget.key));
  }

  function widgetPresentMetrics(widget) {
    return Object.entries((widget && widget.metrics) || {})
      .filter(([, value]) => !(value === null || value === undefined || value === "" || value === "—"))
      .map(([key]) => formatWidgetMetricLabel(key, widget && widget.key));
  }

  /* ==========================================================
   * Diagnostic source trace — maps each widget back to the exact
   * import dataset/file/fields it needs, the live diagnostics status,
   * and the single concrete next action. Real data only; nothing is
   * fabricated. Mirrors import-manifest.json so it works at runtime
   * in the desktop app where the JS manifest loader is unavailable.
   * ========================================================== */
  const DATASET_CONTRACTS = {
    "softdent.dashboard": { label: "SoftDent dashboard export", files: ["softdent_dashboard_data.json"], importDir: "app_data/nr2/document_inbox/softdent", required: ["production"], optional: ["collections", "insurance", "patient", "provider", "period"], automated: true },
    "softdent.claims": { label: "SoftDent claims export", files: ["softdent_claims_export.csv"], importDir: "app_data/nr2/document_inbox/softdent", required: ["ClaimId"], optional: ["PatientName", "Payer", "ServiceDate", "ClaimAmount", "ClaimStatus"], automated: true },
    "softdent.clinicalNotes": { label: "SoftDent clinical notes export", files: ["softdent_clinical_notes_data.json"], importDir: "app_data/nr2/document_inbox/softdent", required: [], optional: ["PatientName", "Provider", "NoteDate", "NoteText"], automated: true },
    "softdent.ar": { label: "SoftDent A/R aging export", files: ["softdent_ar_aging.csv"], importDir: "app_data/nr2/document_inbox/softdent", required: ["Bucket"], optional: ["Balance"], automated: true },
    "softdent.newPatients": { label: "SoftDent new patients export", files: ["softdent_new_patients.csv"], importDir: "app_data/nr2/document_inbox/softdent", required: ["Count"], optional: ["Period"], automated: true, generatedBy: ["softdent_practice_exports.py"] },
    "softdent.treatmentPlans": { label: "SoftDent treatment plan summary export", files: ["treatment_plan_summary.csv"], importDir: "app_data/nr2/document_inbox/softdent", required: [], optional: ["Presented", "Accepted", "Amount"], automated: true, generatedBy: ["softdent_practice_exports.py"] },
    "softdent.caseAcceptance": { label: "SoftDent case acceptance export", files: ["case_acceptance.csv"], importDir: "app_data/nr2/document_inbox/softdent", required: [], optional: ["AcceptanceRate", "Presented", "Accepted"], automated: true, generatedBy: ["softdent_practice_exports.py"] },
    "softdent.hygieneRecall": { label: "SoftDent hygiene recall export", files: ["hygiene_recall_summary.csv"], importDir: "app_data/nr2/document_inbox/softdent", required: [], optional: ["Period", "HygieneCompleted", "RecallDue"], automated: true, generatedBy: ["softdent_practice_exports.py"] },
    "softdent.operatory": { label: "SoftDent operatory schedule export", files: ["operatory_schedule.json", "softdent_operatory_chairs.json"], importDir: "app_data/nr2/document_inbox/softdent", required: ["operatoryChairs"], optional: [], automated: true, generatedBy: ["softdent_practice_exports.py"] },
    "quickbooks.revenue": { label: "QuickBooks revenue/P&L export", files: ["quickbooks_revenue.csv"], importDir: "app_data/nr2/document_inbox/quickbooks", required: ["TotalIncome"], optional: ["Month"], automated: true },
    "quickbooks.expenses": { label: "QuickBooks expenses export", files: ["quickbooks_expenses.csv"], importDir: "app_data/nr2/document_inbox/quickbooks", required: ["TotalExpense"], optional: ["Month"], automated: true },
    "quickbooks.expenseCategories": { label: "QuickBooks expense categories export", files: ["quickbooks_expense_categories.csv"], importDir: "app_data/nr2/document_inbox/quickbooks", required: ["Category"], optional: ["Amount", "Period", "Scope"], automated: true },
    "quickbooks.ar": { label: "QuickBooks A/R export", files: ["quickbooks_ar.csv"], importDir: "app_data/nr2/document_inbox/quickbooks", required: ["Bucket"], optional: ["Balance"], automated: true },
    "local:documents": { label: "Local accounting documents", files: ["app_data/nr2/document_inbox (drop)", "app_data/nr2/document_inbox/softdent", "app_data/nr2/document_inbox/quickbooks", "document_source_import.py", "sync_document_sources.py", "app_data/nr2/accounting_documents.sqlite3 (OCR ledger)", "nr2:v2:documents (desktop store)"], importDir: "app_data/nr2/document_inbox", required: [], optional: [], automated: true, local: true },
    "local:narratives": { label: "Local narrative drafts", files: ["(local narrative drafts)"], importDir: "local records", required: [], optional: [], automated: true, local: true },
    "local:library": { label: "Local library documents", files: ["(local indexed library)"], importDir: "local records", required: [], optional: [], automated: true, local: true },
  };

  const WIDGET_DATASETS = {
    practiceFinancialOverview: ["quickbooks.revenue", "softdent.dashboard"],
    financialProductionTrend: ["softdent.dashboard"],
    payerMixAndCollections: ["softdent.dashboard"],
    providerPerformance: ["softdent.dashboard"],
    ebitdaNormalization: ["quickbooks.expenses", "quickbooks.expenseCategories"],
    quickbooksProfitLossDetail: ["quickbooks.revenue", "quickbooks.expenses"],
    quickbooksExpenseBreakdown: ["quickbooks.expenses"],
    accountsPayableAutomation: ["local:documents", "quickbooks.expenses"],
    documentIntakeQueue: ["local:documents"],
    documentPreview: ["local:documents"],
    periodCloseAndPosting: ["local:documents"],
    journalPostingQueue: ["local:documents"],
    smartClaimsAndReceivables: ["softdent.claims", "softdent.ar"],
    claimsPipeline: ["softdent.claims"],
    arAgingAndCollections: ["softdent.ar"],
    arOutstandingClaims: ["softdent.claims", "softdent.ar"],
    careDeliveryPerformance: ["softdent.dashboard", "softdent.ar"],
    softdentArAging: ["softdent.ar"],
    softdentResponsibility: ["softdent.dashboard"],
    newPatients: ["softdent.newPatients"],
    treatmentPlanSummary: ["softdent.treatmentPlans"],
    caseAcceptance: ["softdent.caseAcceptance"],
    hygieneRecall: ["softdent.hygieneRecall"],
    softdentOperatoryGrid: ["softdent.operatory"],
    narrativeWorkflow: ["local:narratives", "softdent.claims"],
    documentLibrary: ["local:library"],
  };

  function diagnosticsByDatasetKey(snapshot) {
    const bundle = snapshot && snapshot.importBundle;
    const diagnostics =
      (bundle && bundle.diagnostics) ||
      (bundle && typeof ImportDiagnostics !== "undefined" ? ImportDiagnostics.evaluateBundle(bundle) : null) ||
      (bundle && typeof window !== "undefined" && window.ImportDiagnostics ? window.ImportDiagnostics.evaluateBundle(bundle) : null);
    const map = {};
    if (diagnostics && Array.isArray(diagnostics.datasets)) {
      diagnostics.datasets.forEach((item) => {
        if (item && item.datasetKey) map[item.datasetKey] = item;
      });
    }
    return map;
  }

  function datasetNextAction(contract, diag, missingMetrics) {
    if (contract.local) {
      if (contract.label === "Local accounting documents") {
        return "HAL reads financial numbers from SoftDent and QuickBooks import cache only — not individual invoices. Use Add document for manual entries.";
      }
      return `Add ${contract.label.toLowerCase()} in the app — no import file is required.`;
    }
    const file = (contract.files && contract.files[0]) || "the export file";
    const status = diag ? diag.status : "missing";
    if (!contract.automated || status === "not_configured") {
      return `Enable and export ${file} (not yet automated) into ${contract.importDir}.`;
    }
    if (status === "missing" || !diag || !diag.found) {
      if (diag && diag.upstreamFile) {
        return `Upstream ${file} exists but was not copied — run "refresh imports".`;
      }
      return `Add ${file} into ${contract.importDir}, then run "refresh imports".`;
    }
    if (status === "stale") {
      return `Re-export ${file} (current copy is stale), then run "refresh imports".`;
    }
    const failures = (diag && diag.requiredFieldFailures) || [];
    if (failures.length) {
      return `Export ${file} including required fields: ${failures.join(", ")}.`;
    }
    if (diag && diag.rowCount === 0) {
      return `Export ${file} with at least one data row.`;
    }
    if (missingMetrics && missingMetrics.length) {
      return `Export ${file} with populated values for: ${missingMetrics.join(", ")}.`;
    }
    return `Verify ${file} contains complete current-period values.`;
  }

  function buildWidgetSourceTrace(feed, snapshot) {
    if (!feed || !feed.widgets) return [];
    const diagMap = diagnosticsByDatasetKey(snapshot);
    return WIDGET_ORDER.map((key) => {
      const widget = feed.widgets[key];
      if (!widget) return null;
      const status = String(widget.status || "FAILED").toUpperCase();
      const present = widgetPresentMetrics(widget);
      const missing = widgetMissingMetrics(widget);
      const datasetKeys = WIDGET_DATASETS[key] || [];
      const sources = datasetKeys.map((dk) => {
        const contract = DATASET_CONTRACTS[dk] || { label: dk, files: [], importDir: "", required: [], optional: [], automated: true };
        const diag = diagMap[dk] || null;
        return {
          datasetKey: dk,
          label: contract.label,
          files: contract.files || [],
          requiredFields: contract.required || [],
          local: Boolean(contract.local),
          diagnosticStatus: diag ? diag.status : contract.local ? "local" : "missing",
          found: diag ? Boolean(diag.found) : false,
          rowCount: diag ? diag.rowCount || 0 : 0,
          sourceFile: diag ? diag.sourceFile : null,
          missingFields: diag ? diag.requiredFieldFailures || [] : [],
          detail: diag ? diag.detail : null,
        };
      });
      let nextAction;
      if (status === "SUCCESS") {
        nextAction = "Filled from current verified data — no action needed.";
      } else {
        const ranked = ["missing", "not_configured", "partial", "stale", "connected", "local"];
        const worst = sources
          .slice()
          .sort((a, b) => ranked.indexOf(a.diagnosticStatus) - ranked.indexOf(b.diagnosticStatus))[0];
        const contract = worst ? DATASET_CONTRACTS[worst.datasetKey] : null;
        nextAction = contract ? datasetNextAction(contract, diagMap[worst.datasetKey] || null, missing) : "Add the required source data.";
      }
      return { key, title: widget.title || key, status, presentMetrics: present, missingMetrics: missing, sources, nextAction };
    }).filter(Boolean);
  }

  function formatWidgetSourceTrace(feed, snapshot) {
    if (!feed || !feed.widgets) return "No widget feed is available yet. Refresh imports, then ask again.";
    const trace = buildWidgetSourceTrace(feed, snapshot);
    const counts = trace.reduce(
      (acc, t) => {
        if (t.status === "SUCCESS") acc.ready += 1;
        else if (t.status === "DEGRADED") acc.partial += 1;
        else acc.empty += 1;
        return acc;
      },
      { ready: 0, partial: 0, empty: 0 },
    );
    const lines = [
      "HAL widget source trace (real data only — each widget mapped to its exact source):",
      `Summary: ${counts.ready} ready · ${counts.partial} partial · ${counts.empty} waiting on a source.`,
      "",
    ];
    trace.forEach((t) => {
      lines.push(`[${t.status}] ${t.title}`);
      t.sources.forEach((s) => {
        const fileText = s.files && s.files.length ? s.files.join(", ") : "(local records)";
        const statusBit = s.local ? "local records" : `${s.diagnosticStatus}${s.found ? `, ${s.rowCount} row(s)` : ", file not found"}`;
        const reqBit = s.requiredFields && s.requiredFields.length ? ` · requires: ${s.requiredFields.join(", ")}` : "";
        const missBit = s.missingFields && s.missingFields.length ? ` · missing fields: ${s.missingFields.join(", ")}` : "";
        lines.push(`  Source: ${s.label} (${fileText}) — ${statusBit}${reqBit}${missBit}`);
      });
      if (t.presentMetrics.length) lines.push(`  Found: ${t.presentMetrics.join(", ")}`);
      if (t.missingMetrics.length) lines.push(`  Empty: ${t.missingMetrics.join(", ")}`);
      lines.push(`  Next: ${t.nextAction}`);
      lines.push("");
    });
    lines.push("HAL leaves blanks as blanks until the real export or local record exists. Nothing is mocked, posted, or written back.");
    return lines.join("\n");
  }

  function formatPostingQueueList(payload) {
    const data = payload || {};
    const items = Array.isArray(data.items) ? data.items : [];
    const metrics = data.metrics || {};
    const pending = metrics.pendingReview != null ? metrics.pendingReview : metrics.pending;
    const approved = metrics.approved != null ? metrics.approved : metrics.ready;
    const lines = [
      "Journal posting queue (local SQLite — draft/review only; staff posts to QuickBooks outside NR2):",
      `Pending review ${pending != null ? pending : "—"} · Approved ${approved != null ? approved : "—"} · Total ${metrics.total != null ? metrics.total : items.length}`,
    ];
    if (data.unavailable) {
      lines.push("", "Live queue access needs the NR2 server. Run StartProgram.bat and open http://127.0.0.1:8765/.");
      return lines.join("\n");
    }
    if (!items.length) {
      lines.push("", "No queue entries yet. Mark a reviewed document Posted with “Queue journal draft” checked, or ask me to draft a journal entry.");
      return lines.join("\n");
    }
    lines.push("");
    items.slice(0, 12).forEach((entry) => {
      const id = entry.queue_id || entry.id || "—";
      const status = entry.status || "pending_review";
      const amount = entry.amount != null ? entry.amount : "—";
      const period = entry.accounting_period || entry.period || "—";
      const desc = String(entry.description || entry.memo || "Journal draft").slice(0, 72);
      lines.push(`- [${status}] ${id} · ${period} · $${amount} — ${desc}`);
    });
    if (items.length > 12) lines.push(`… and ${items.length - 12} more. Open Documents for the full queue panel.`);
    lines.push("", "Next step: review pending rows on Documents, approve for export, then staff enters approved CSV in QuickBooks.");
    return lines.join("\n");
  }

  function formatWidgetFeed(feed) {
    const lines = [`Manager dashboard widgets (${feed.manager}, local only):`, ""];
    WIDGET_ORDER.forEach((key) => {
      const w = feed.widgets[key];
      if (!w) return;
      lines.push(`[${w.status}] ${w.title} — ${w.summary}`);
      lines.push(`  ${formatWidgetMetrics(w)}`);
    });
    lines.push("", `Publish job: ${feed.jobs.widgetPublish.status}. Local-only; A/R shown only from a verified source.`);
    return lines.join("\n");
  }

  function formatWidgetFillSuggestions(feed) {
    if (!feed || !feed.widgets) return "No widget feed is available yet. Refresh imports, then ask again.";
    const lines = [
      "Suggestions to fill all manager widgets (real data only):",
      "",
      "Start with these sources:",
      "1. SoftDent dashboard export for production, collections, responsibility split, and provider performance.",
      "2. SoftDent claims export plus verified SoftDent A/R aging export for claims, receivables, and aging widgets.",
      "3. QuickBooks revenue/P&L and expenses exports for financial, EBITDA, and sync-health widgets.",
      "4. Local accounting documents, narrative drafts, and library documents for document/narrative/library widgets.",
      "",
      "Widget-by-widget fill list:",
    ];
    WIDGET_ORDER.forEach((key) => {
      const widget = feed.widgets[key];
      if (!widget) return;
      const requirements = WIDGET_FILL_REQUIREMENTS[key] || ["Verified local/import data for this widget"];
      const missing = widgetMissingMetrics(widget);
      const status = String(widget.status || "UNKNOWN").toUpperCase();
      const prefix = status === "SUCCESS" ? "Keep filled" : "Fill";
      lines.push(`- [${status}] ${widget.title}: ${prefix} with ${requirements.join("; ")}.`);
      if (missing.length) lines.push(`  Missing/empty metrics: ${missing.join(", ")}.`);
    });
    lines.push("", "HAL must leave blanks as blanks until the real export or local record exists. Nothing is mocked, posted, or written back.");
    return lines.join("\n");
  }

  function formatWidgetMissingData(feed) {
    if (!feed || !feed.widgets) return "No widget feed is available yet. Refresh imports, then ask again.";
    const lines = ["Missing data by widget (real data only):", ""];
    WIDGET_ORDER.forEach((key) => {
      const widget = feed.widgets[key];
      if (!widget) return;
      const missing = widgetMissingMetrics(widget);
      const requirements = WIDGET_FILL_REQUIREMENTS[key] || ["Verified local/import data for this widget"];
      if (String(widget.status).toUpperCase() === "SUCCESS" && !missing.length) {
        lines.push(`- [SUCCESS] ${widget.title}: filled from current verified data.`);
      } else {
        lines.push(`- [${widget.status}] ${widget.title}: ${missing.length ? missing.join(", ") : "source is incomplete or degraded"}.`);
        lines.push(`  Needed: ${requirements.join("; ")}.`);
      }
    });
    lines.push("", "Do not fill these with estimates. Import or add the real source data first.");
    return lines.join("\n");
  }

  function formatWidgetFillPriority(feed) {
    if (!feed || !feed.widgets) return "No widget feed is available yet. Refresh imports, then ask again.";
    const priority = [
      "practiceFinancialOverview",
      "quickbooksProfitLossDetail",
      "arAgingAndCollections",
      "smartClaimsAndReceivables",
      "claimsPipeline",
      "providerPerformance",
      "payerMixAndCollections",
      "financialProductionTrend",
      "softdentArAging",
      "softdentResponsibility",
      "careDeliveryPerformance",
      "ebitdaNormalization",
      "accountsPayableAutomation",
      "documentIntakeQueue",
      "documentPreview",
      "periodCloseAndPosting",
      "journalPostingQueue",
      "narrativeWorkflow",
      "documentLibrary",
      "arOutstandingClaims",
    ];
    const lines = ["Priority order to fill widgets:", ""];
    priority.forEach((key, index) => {
      const widget = feed.widgets[key];
      if (!widget) return;
      const missing = widgetMissingMetrics(widget);
      lines.push(`${index + 1}. [${widget.status}] ${widget.title} — ${(WIDGET_FILL_REQUIREMENTS[key] || []).join("; ") || "verified local/import data"}`);
      if (missing.length) lines.push(`   Missing: ${missing.join(", ")}.`);
    });
    lines.push("", "Rationale: owner financials first, then A/R and claims, then accounting documents, narratives, and library context.");
    return lines.join("\n");
  }

  function formatImportHealthSummary(snapshot) {
    const diag = (snapshot && snapshot.importBundle && snapshot.importBundle.diagnostics) || (snapshot && snapshot.diagnostics);
    const datasets = (diag && diag.datasets) || [];
    const lines = ["Import health summary (missing exports are source-data tasks, not software bugs):", ""];
    if (!datasets.length) {
      lines.push("- Diagnostics not available yet. Refresh imports, then ask again.");
      return lines.join("\n");
    }
    const needsAction = datasets.filter((d) => {
      const status = String((d && d.status) || "").toLowerCase();
      return status === "missing" || status === "not_configured" || status === "partial" || status === "stale";
    });
    if (!needsAction.length) {
      lines.push("- All configured import datasets are connected for the current cache.");
      return lines.join("\n");
    }
    needsAction.forEach((d) => {
      const label = d.datasetKey || d.bundleKey || "dataset";
      const status = String(d.status || "unknown").toUpperCase();
      const detail = d.detail || "Export required before related widgets can populate.";
      lines.push(`- [${status}] ${label}: ${detail}`);
      if (d.collectorHint) lines.push(`  Collector: ${d.collectorHint}`);
    });
    lines.push("", "HAL will not fabricate missing SoftDent claims, clinical notes, new patients, treatment plans, or case acceptance.");
    return lines.join("\n");
  }

  function formatCognitivePathways(halData) {
    const block = (halData && halData.cognitivePathways) || {};
    const pathways = (halData && halData.pathways) || [];
    const lines = [
      block.title || "HAL cognitive & social characteristics",
      block.summary || "",
      "",
      "Cognitive:",
    ];
    (block.cognitive || []).forEach((item) => {
      lines.push(`- ${item.label}: ${item.practice}`);
    });
    lines.push("", "Social & cultural:");
    (block.social || []).forEach((item) => {
      lines.push(`- ${item.label}: ${item.practice}`);
    });
    if (pathways.length) {
      lines.push("", "High-priority pathways:");
      pathways
        .slice()
        .sort((a, b) => (a.priority || 99) - (b.priority || 99))
        .forEach((p) => {
          lines.push(`- [P${p.priority}] ${p.title}: ${p.summary}`);
        });
    }
    return lines.filter(Boolean).join("\n");
  }

  function formatWidgetPeriodRequirements(snapshot) {
    const lib = typeof HalPeriodRequirements !== "undefined" ? HalPeriodRequirements : globalThis.HalPeriodRequirements;
    if (lib && typeof lib.formatWidgetPeriodRequirements === "function") {
      return lib.formatWidgetPeriodRequirements(snapshot);
    }
    return "Widget period requirements module is not loaded.";
  }

  function formatPracticeSourcePullResult(payload) {
    if (!payload) {
      return "Practice source pull unavailable. Run StartProgram.bat with staff approval enabled.";
    }
    if (payload.approved === false) {
      return `Practice source pull blocked: ${payload.error || "Not approved."}`;
    }
    const summary = payload.summary || {};
    const lines = [
      "Authorized practice source pull complete (read-only · nothing written back):",
      "",
      `Mode: ${payload.fullPull ? "FULL (100% upstream exports + live resource scan)" : "standard"}`,
      `SoftDent resources OK: ${summary.softdentResourcesOk ?? "—"}`,
      `QuickBooks resources OK: ${summary.quickbooksResourcesOk ?? "—"}`,
      `Claims verified: ${summary.claimsOk ? "yes" : "no"} (${summary.claimsRowCount ?? 0} row(s))`,
      `Narrative template library: ${summary.narrativeTemplates ?? 100} generic MemoAI-guided drafts`,
      `Document queue count: ${summary.documentQueueCount ?? "—"}`,
    ];
    const claims = payload.claimsVerification || {};
    if (claims.claimIds && claims.claimIds.length) {
      lines.push(`Claim IDs loaded: ${claims.claimIds.slice(0, 6).join(", ")}${claims.claimIds.length > 6 ? "…" : ""}`);
    }
    if (payload.narrativeLibrary && Array.isArray(payload.narrativeLibrary.selections) && payload.narrativeLibrary.selections.length) {
      lines.push("", "Best narrative match per claim (staff review required):");
      payload.narrativeLibrary.selections.slice(0, 4).forEach((sel) => {
        const pick = sel.selected || {};
        lines.push(`- ${sel.claimRef || "—"} → ${pick.id || "—"} (${pick.focus || "—"}, score ${sel.score ?? 0})`);
      });
    }
    if (payload.importSync && payload.importSync.syncedAt) {
      lines.push("", `Import cache synced at: ${payload.importSync.syncedAt}`);
    }
    lines.push("", "Next: ask HAL to draft narrative for a claim, show manager dashboard widgets, or work document workbook.");
    return lines.join("\n");
  }

  function resolveClaimById(snapshot, claimId) {
    const ref = String(claimId || "").trim();
    const claimsBlock = (snapshot && snapshot.claims) || {};
    const claims = claimsBlock.claims || claimsBlock.top || [];
    if (!claims.length) return null;
    if (!ref) return claims[0];
    return (
      claims.find((c) => String(c.id || c.ClaimId || "").toLowerCase() === ref.toLowerCase()) ||
      claims.find((c) => String(c.patient || "").toLowerCase().includes(ref.toLowerCase())) ||
      claims[0]
    );
  }

  function narrativeModelLane(focus, denialReason) {
    const hay = `${focus || ""} ${denialReason || ""}`.toLowerCase();
    if (/\b(denial appeal|alternate benefit|post-operative complication|appeal)\b/.test(hay) || /\bdenied\b/.test(hay)) {
      return "reason24b";
    }
    if (/\b(prior authorization|periodontal|fracture documentation)\b/.test(hay)) {
      return "fast14b";
    }
    return "chat8b";
  }

  function buildDraftInsuranceNarrative(snapshot, params) {
    const lib = typeof HalNarrativeLibrary !== "undefined" ? HalNarrativeLibrary : globalThis.HalNarrativeLibrary;
    const nr = typeof NarrativeReview !== "undefined" ? NarrativeReview : globalThis.NarrativeReview;
    if (!lib || !nr) {
      return { ok: false, summary: "Narrative draft tools are not loaded in this runtime." };
    }
    const p = params || {};
    const claim = resolveClaimById(snapshot, p.claimId || p.claim_id);
    if (!claim) {
      return {
        ok: false,
        summary: "No claims are visible yet. Load the SoftDent claims export before drafting narratives.",
        missingFields: ["missing_softdent_claims_export"],
        citationWidgets: ["claimsPipeline"],
      };
    }
    const focus = p.focus || (lib.selectBestNarrativeForClaim(claim).selected || {}).focus || "Medical Necessity";
    const tone = p.tone || "Professional";
    const length = p.length || "Standard";
    const denialReason = p.denialReason || p.denial_reason || claim.denialReason || "";
    const packet = nr.buildCasePacket(claim, snapshot, { focus, denialReason });
    const library = lib.buildGenericDraftLibrary();
    const match =
      library.find((row) => row.focus === focus && row.tone === tone && row.length === length) ||
      (lib.selectBestNarrativeForClaim(claim, library).selected || library[0]);
    const facts = (packet.source_facts || []).filter((f) => f.text && !/empty/i.test(f.text));
    const factLines = facts.map((f) => `${f.text} [${f.fact_id}]`).join(" ");
    const lead = match ? match.text.split(".")[0] + "." : `Clinical summary for ${focus.toLowerCase()}.`;
    const bodyParts = [lead];
    if (factLines) bodyParts.push(`Supporting chart notes: ${factLines}`);
    else bodyParts.push("No imported clinical note text was available — staff must add findings manually.");
    if (denialReason) bodyParts.push(`Payer denial context (from claim export): ${denialReason}`);
    bodyParts.push(
      length === "Brief"
        ? "Staff review required before any payer submission. Local draft only — not submitted."
        : "Based on documented findings, the proposed procedure is medically necessary. Human review required; not submitted.",
    );
    const text = bodyParts.join(" ");
    const validation = nr.validateDraftPayload({ text, claim, packet, snapshot, focus, tone, length });
    const citationWidgets = ["narrativeWorkflow", "claimsPipeline"];
    if (facts.length) citationWidgets.push("softdent.clinicalNotes");
    return {
      ok: validation.ok,
      summary: validation.ok
        ? `Draft ready for human review · ${claim.id || "claim"} · ${focus} · ${tone}`
        : `Draft blocked: ${(validation.issues || []).slice(0, 3).join("; ")}`,
      text,
      focus,
      tone,
      length,
      claimId: claim.id || p.claimId,
      patient: claim.patient,
      missingFields: validation.missingFields || [],
      citationWidgets: Array.from(new Set(citationWidgets)),
      citations: facts.map((f) => ({ fact_id: f.fact_id, excerpt: f.text })),
      draftStatus: validation.status,
      modelLane: narrativeModelLane(focus, denialReason),
      packet_id: packet.packet_id,
      draft_id: packet.draft_id,
      localOnly: true,
      notSubmitted: true,
    };
  }

  function formatDraftInsuranceNarrativeResult(result) {
    if (!result || result.ok === false) {
      return result && result.summary
        ? result.summary
        : "Narrative draft could not be prepared — verify claims and clinical notes exports.";
    }
    const lines = [
      `Insurance narrative draft (local only · ${result.modelLane || "chat8b"} lane):`,
      "",
      `Claim: ${result.claimId || "—"} · Patient: ${result.patient || "—"}`,
      `Focus: ${result.focus} · Tone: ${result.tone} · Status: ${result.draftStatus}`,
    ];
    if (result.missingFields && result.missingFields.length) {
      lines.push(`Missing / flagged: ${result.missingFields.join(", ")}`);
    }
    lines.push("", "Draft (staff must review; not submitted):", result.text || "");
    lines.push("", "Nothing has been sent to a payer.");
    return lines.join("\n");
  }

  const SD_EXTRACT_TABLES = [
    "sd_patients",
    "sd_procedures",
    "sd_payments",
    "sd_claims",
    "sd_appointments",
    "sd_providers",
    "sd_adjustments",
  ];

  function buildSoftdentExtractStatus(snapshot) {
    const snap = snapshot || {};
    const health = snap.health || snap.runtimeHealth || {};
    const bundle = snap.importBundle || {};
    const odbcLane = (bundle.softdent && bundle.softdent.odbcExtract) || {};
    const tableCounts = (snap.softdentOdbcStatus && snap.softdentOdbcStatus.tableCounts) || {};
    return {
      lastExtractAt: health.lastOdbcExtract || odbcLane.refreshedAt || null,
      lastMode: health.softdentOdbcMode || odbcLane.mode || null,
      populatedTables: health.softdentSdTablesPopulated != null ? health.softdentSdTablesPopulated : odbcLane.populatedTables,
      odbcConfigured: snap.softdentOdbcStatus ? snap.softdentOdbcStatus.odbcConfigured : null,
      queriesConfigured: snap.softdentOdbcStatus ? snap.softdentOdbcStatus.queriesConfigured : null,
      tableCounts,
      nextSteps: (snap.softdentOdbcStatus && snap.softdentOdbcStatus.nextSteps) || [],
    };
  }

  function formatSoftdentExtractStatus(status) {
    const s = status || {};
    const mode = s.lastMode || "none";
    const populated = s.populatedTables != null ? s.populatedTables : 0;
    const lines = [
      "SoftDent extract lane (sd_* SQLite tables):",
      `- Last extract: ${s.lastExtractAt || "never"}`,
      `- Mode: ${mode}${s.stale ? " (stale)" : ""}`,
      `- ODBC DSN configured: ${s.odbcConfigured === true ? "yes" : s.odbcConfigured === false ? "no" : "unknown"}`,
      `- SQL queries configured: ${s.queriesConfigured != null ? s.queriesConfigured : "unknown"}`,
      `- Populated tables: ${populated}/7`,
    ];
    const counts = s.tableCounts || {};
    const countBits = SD_EXTRACT_TABLES.map((table) => `${table.replace("sd_", "")}=${counts[table] != null ? counts[table] : "—"}`);
    if (countBits.length) lines.push(`- Row counts: ${countBits.join(", ")}`);
    const steps = Array.isArray(s.nextSteps) ? s.nextSteps : [];
    if (steps.length) {
      lines.push("", "Next steps:");
      steps.slice(0, 4).forEach((step) => lines.push(`- ${step}`));
    }
    if (mode === "json-fallback") {
      lines.push("", "JSON/daysheet fallback is active — ODBC deep extract is optional until IT configures read-only SQL access.");
    } else if (mode === "sensei-datasync" || mode === "sensei+json-fallback") {
      lines.push("", "Sensei DataSync lane is active — sd_* tables refresh from live Carestream Gateway JSON on this SoftDent server.");
    }
    return lines.join("\n");
  }

  function formatNarrativeForClaim(snapshot, query) {
    const lib = typeof HalNarrativeLibrary !== "undefined" ? HalNarrativeLibrary : globalThis.HalNarrativeLibrary;
    if (!lib) return "Narrative library is not loaded in this runtime.";
    const claim = lib.resolveClaimFromQuery(query, snapshot);
    if (!claim) return "No claims are visible yet. Run a full practice source pull and verify the SoftDent claims export.";
    const selection = lib.selectBestNarrativeForClaim(claim);
    return lib.formatNarrativeSelectionAnswer(selection, claim);
  }

  function formatHalJobRequirements(feed, snapshot) {
    const snap = snapshot || {};
    const widgets = (feed && feed.widgets) || {};
    const bundle = snap.importBundle || {};
    const failed = WIDGET_ORDER.filter((key) => widgets[key] && String(widgets[key].status).toUpperCase() === "FAILED").map(
      (key) => widgets[key],
    );
    const degraded = WIDGET_ORDER.filter((key) => widgets[key] && String(widgets[key].status).toUpperCase() === "DEGRADED").map(
      (key) => widgets[key],
    );
    const missing = formatWidgetMissingData(feed);
    const lines = [
      "HAL job requirements — what I still need to do my work (local read-only only):",
      "",
      `Widget posture: ${failed.length} failed · ${degraded.length} degraded · ${WIDGET_ORDER.length - failed.length - degraded.length} ready`,
    ];
    if (snap.documents && snap.documents.queueCount) {
      lines.push(
        `Documents page: ${snap.documents.queueCount} rows loaded (QuickBooks ${snap.documents.sourceCounts?.quickbooks || 0}, SoftDent ${snap.documents.sourceCounts?.softdent || 0}, OCR ${snap.documents.sourceCounts?.ocr || 0}).`,
      );
    } else {
      lines.push("Documents page: queue empty — run practice source pull or drop OCR files in document inbox.");
    }
    lines.push("", "Still missing or partial for full widget coverage:");
    if (failed.length) {
      failed.slice(0, 12).forEach((widget) => {
        lines.push(`- [FAILED] ${widget.title}: ${widget.summary || ""}`);
        const gaps = widgetMissingMetrics(widget);
        if (gaps.length) lines.push(`  Needs: ${gaps.join(", ")}`);
      });
    }
    if (degraded.length) {
      degraded.slice(0, 8).forEach((widget) => {
        lines.push(`- [DEGRADED] ${widget.title}`);
        const gaps = widgetMissingMetrics(widget);
        if (gaps.length) lines.push(`  Needs: ${gaps.join(", ")}`);
      });
    }
    if (!failed.length && !degraded.length) {
      lines.push("- None — all canonical widgets have verified data in the current snapshot.");
    }
    lines.push("", "Staff actions (exports / configuration):");
    const checklist = formatImportChecklist(feed, snapshot);
    const actionLines = checklist
      .split("\n")
      .filter((line) => /^\d+\./.test(line.trim()) || line.includes("Fills:") || line.includes("Needs current"))
      .slice(0, 10);
    if (actionLines.length) actionLines.forEach((line) => lines.push(line));
    else lines.push("- Keep SoftDent and QuickBooks exports fresh in document_inbox folders.");
    lines.push("", "Operational review (not missing data):");
    if (snap.documents && snap.documents.posting) {
      const pending = (snap.documents.posting.find((p) => /pending/i.test(p.label)) || {}).count || 0;
      if (pending) lines.push(`- ${pending} document(s) still Pending Review before posting.`);
    }
    lines.push("- Posting to QuickBooks remains human-reviewed only.");
    lines.push("", missing ? "Missing-data detail:" : "");
    if (missing) lines.push(missing);
    return lines.filter(Boolean).join("\n");
  }

  function formatImportChecklist(feed, snapshot) {
    const qbStatus = feed?.sources?.quickbooks?.lastStatus || "UNKNOWN";
    const sdStatus = feed?.sources?.softdent?.lastStatus || "UNKNOWN";
    const health = snapshot ? formatImportHealthSummary(snapshot) : "";
    return [
      "Import checklist to fill widgets:",
      "",
      "HAL reads SoftDent/QuickBooks exports only from document-inbox folders below. Auto-pull copies upstream exports into those same folders.",
      "",
      `1. SoftDent dashboard export -> app_data/nr2/document_inbox/softdent/ (current status: ${sdStatus})`,
      "   Fills: production, collections, provider performance for Dr. Michael Reno, responsibility split, SoftDent source health.",
      "   Needs current AND prior month rows for trend/YTD widgets (partial if only one month present).",
      "2. SoftDent claims export -> app_data/nr2/document_inbox/softdent/",
      "   Fills: claims pipeline, claim readiness, outstanding claims, narrative source facts.",
      "3. Verified SoftDent A/R aging export -> app_data/nr2/document_inbox/softdent/",
      "   Fills: A/R aging, receivables, patient/insurance balances. HAL will not fabricate A/R.",
      `4. QuickBooks revenue/P&L export -> app_data/nr2/document_inbox/quickbooks/ (current status: ${qbStatus})`,
      "   Fills: practice financial overview, P&L detail, revenue, net income.",
      "5. QuickBooks expenses export -> app_data/nr2/document_inbox/quickbooks/",
      "   Fills: expenses, EBITDA candidates, accounting review queue.",
      "6. SoftDent new patients, treatment plans, and case acceptance exports (if those widgets are needed).",
      "7. Local accounting documents, library files, and narrative drafts.",
      "   Fills: document intake, selected document preview, period close, narrative workflow, document library.",
      "",
      health ? `${health}\n` : "",
      "After copying files, ask HAL: refresh imports. HAL reads only; nothing is written back.",
    ].join("\n");
  }

  function resolvePracticeSourceRequest(query) {
    const q = String(query || "").toLowerCase();
    let system = null;
    if (/\bquickbooks\b|\bqb\b/.test(q)) system = "quickbooks";
    if (/\bsoftdent\b|\bsoft dent\b/.test(q)) system = system || "softdent";
    let resource = "catalog";
    if (/\b(catalog|what can (you|hal)|everything|anything|list resources)\b/.test(q)) resource = "catalog";
    else if (/\ball\b/.test(q) && system) resource = "all";
    else if (/\bclaims?\b/.test(q)) resource = "claims";
    else if (/\bclinical\b/.test(q)) resource = "clinical_notes";
    else if (/\bbridge\b/.test(q)) resource = "bridge";
    else if (/\bnew patients?\b/.test(q)) resource = "new_patients";
    else if (/\btreatment plan/.test(q)) resource = "treatment_plans";
    else if (/\bcase acceptance\b/.test(q)) resource = "case_acceptance";
    else if (/\bprobe\b/.test(q)) resource = "probe_summary";
    else if (/\bmonthly\b|\bpnl\b|\bp&l\b|profit/.test(q)) resource = /\bquickbooks\b|\bqb\b/.test(q) ? "monthly_pnl" : "dashboard";
    else if (/\brevenue\b|\bincome\b/.test(q)) resource = /\bquickbooks\b|\bqb\b/.test(q) ? "revenue" : "dashboard";
    else if (/\bexpenses?\b/.test(q)) resource = "expenses";
    else if (/\bexpense categor/.test(q)) resource = "expense_categories";
    else if (/\ba\/?r\b|\breceivable/.test(q)) resource = /\bsoftdent\b/.test(q) ? "ar" : "ar";
    else if (/\bdashboard\b|\bproduction\b|\bcollections\b/.test(q)) resource = "dashboard";
    const refreshCache = /\b(refresh|stage|pull fresh|sync)\b/.test(q);
    return { system: system || "catalog", resource, refreshCache };
  }

  function formatPracticeSourceCatalog(catalog) {
    if (!catalog || !catalog.systems) {
      return "Practice source catalog unavailable. Run StartProgram.bat to query QuickBooks and SoftDent directly.";
    }
    const lines = [
      "Authorized practice source catalog (read-only direct access):",
      "",
      catalog.policy || "HAL may read upstream sources locally; nothing is posted back.",
      "",
      `Auto-pull into document page: ${catalog.autoPullEnabled ? "enabled" : "disabled"}`,
      `SoftDent cache: ${catalog.cacheDirs?.softdent || "—"}`,
      `QuickBooks cache: ${catalog.cacheDirs?.quickbooks || "—"}`,
      "",
      "QuickBooks resources HAL can fetch directly:",
    ];
    Object.entries(catalog.systems.quickbooks?.resources || {}).forEach(([key, label]) => {
      lines.push(`- ${key}: ${label}`);
    });
    lines.push("", "SoftDent resources HAL can fetch directly:");
    Object.entries(catalog.systems.softdent?.resources || {}).forEach(([key, label]) => {
      lines.push(`- ${key}: ${label}`);
    });
    lines.push(
      "",
      "Examples:",
      '- "fetch quickbooks revenue directly"',
      '- "pull softdent claims from source"',
      '- "get everything from quickbooks"',
      '- "refresh and fetch quickbooks monthly pnl"',
    );
    return lines.join("\n");
  }

  function formatPracticeSourceFetch(result, request) {
    if (!result) {
      return "Direct source fetch unavailable. Run StartProgram.bat and ensure QuickBooks Desktop / SoftDent exports are reachable.";
    }
    const lines = [
      "Authorized direct source fetch (read-only):",
      "",
      `System: ${result.system || request?.system || "—"}`,
      `Resource: ${result.resource || request?.resource || "—"}`,
      `Fetched: ${result.fetchedAt || "—"}`,
    ];
    if (result.refreshResult) {
      lines.push("Import cache refreshed before fetch.");
    }
    if (result.results) {
      lines.push("", "Batch results:");
      Object.entries(result.results).forEach(([key, item]) => {
        lines.push(`- ${key}: ${item.ok ? `ok (${item.rowCount ?? "?"} rows)` : `failed — ${item.error || "unknown"}`}`);
      });
      return lines.join("\n");
    }
    if (!result.ok) {
      lines.push("", `Failed: ${result.error || "unknown error"}`);
      return lines.join("\n");
    }
    lines.push(`Source: ${result.sourceKind || result.label || "direct"}`);
    if (result.sourcePath) lines.push(`Path: ${result.sourcePath}`);
    if (result.sourceFile) lines.push(`File: ${result.sourceFile}`);
    if (result.rowCount != null) lines.push(`Rows: ${result.rowCount}`);
    if (Array.isArray(result.rows) && result.rows.length) {
      lines.push("", "Sample rows:");
      result.rows.slice(0, 5).forEach((row, index) => {
        lines.push(`${index + 1}. ${JSON.stringify(row)}`);
      });
      if (result.rows.length > 5) lines.push(`… ${result.rows.length - 5} more row(s) not shown.`);
    } else if (result.payload && typeof result.payload === "object") {
      lines.push("", "Payload sample:", JSON.stringify(result.payload, null, 2).slice(0, 1200));
    } else if (result.monthly) {
      lines.push("", "Monthly sync:", JSON.stringify(result.monthly, null, 2).slice(0, 1200));
    }
    lines.push("", "HAL read this directly as an authorized practice employee. Nothing was posted back.");
    return lines.join("\n");
  }

  function formatDataQualityCheck(feed) {
    if (!feed || !feed.widgets) return "No widget feed is available yet. Refresh imports, then ask again.";
    const failed = WIDGET_ORDER.map((key) => feed.widgets[key]).filter((w) => w && String(w.status).toUpperCase() === "FAILED");
    const degraded = WIDGET_ORDER.map((key) => feed.widgets[key]).filter((w) => w && String(w.status).toUpperCase() === "DEGRADED");
    const lines = [
      "Data quality check before recommendations:",
      "",
      `Widget publish status: ${feed.jobs?.widgetPublish?.status || "UNKNOWN"}`,
      `Accounting/excel validation: ${feed.accountingExcelValidation?.status || "UNKNOWN"}`,
      `Failed widgets: ${failed.length}`,
      `Degraded widgets: ${degraded.length}`,
      "",
      "Checks HAL should perform:",
      "1. Confirm SoftDent and QuickBooks import freshness before using totals.",
      "2. Leave A/R blank unless a verified SoftDent A/R export exists.",
      "3. Confirm provider performance is only Dr. Michael Reno.",
      "4. Compare SoftDent collections to QuickBooks revenue as a review signal — not production to revenue.",
      "5. Flag blanks, conflicting periods, zero collections with production, and missing document metadata before recommendations.",
    ];
    if (feed.accountingExcelValidation?.issues?.length) {
      lines.push("", "Accounting validation issues:");
      feed.accountingExcelValidation.issues.slice(0, 8).forEach((issue) => {
        lines.push(`- [${issue.severity}] ${issue.widgetKey}: ${issue.message}`);
      });
    }
    if (degraded.length) lines.push("", "Degraded: " + degraded.map((w) => w.title).join(", "));
    if (failed.length) lines.push("Failed: " + failed.map((w) => w.title).join(", "));
    return lines.join("\n");
  }

  function formatEmptyWidgetExplanation(feed, question) {
    if (!feed || !feed.widgets) return "No widget feed is available yet. Refresh imports, then ask again.";
    const q = String(question || "").toLowerCase();
    const matchedKey =
      WIDGET_ORDER.find((key) => q.includes(String(feed.widgets[key]?.title || "").toLowerCase())) ||
      WIDGET_ORDER.find((key) => key && q.includes(key.toLowerCase()));
    const keys = matchedKey ? [matchedKey] : WIDGET_ORDER.filter((key) => String(feed.widgets[key]?.status || "").toUpperCase() !== "SUCCESS");
    const lines = [matchedKey ? "Why this widget is empty or incomplete:" : "Why widgets are empty or incomplete:", ""];
    keys.forEach((key) => {
      const widget = feed.widgets[key];
      if (!widget) return;
      const missing = widgetMissingMetrics(widget);
      lines.push(`- [${widget.status}] ${widget.title}: ${widget.summary}`);
      lines.push(`  Needs: ${(WIDGET_FILL_REQUIREMENTS[key] || ["verified local/import data"]).join("; ")}.`);
      if (missing.length) lines.push(`  Missing metrics: ${missing.join(", ")}.`);
    });
    lines.push("", "If a widget is SUCCESS but visually blank, refresh imports and reopen the related page.");
    return lines.join("\n");
  }

  function formatDailyOwnerBriefing(feed, snapshot) {
    const widgets = (feed && feed.widgets) || {};
    const fin = widgets.practiceFinancialOverview;
    const ar = widgets.arAgingAndCollections;
    const claims = widgets.claimsPipeline;
    const qb = widgets.quickbooksProfitLossDetail;
    const sd = widgets.careDeliveryPerformance;
    const recommendations = [
      "Review A/R only from verified SoftDent A/R export.",
      "Work claims in Needs Review before any payer-facing step.",
      "Use accounting review queue for QuickBooks/documents before any posting decision.",
    ];
    return [
      "Daily owner briefing (local read-only):",
      "",
      `Financial: ${fin ? `[${fin.status}] ${formatWidgetMetrics(fin)}` : "No financial widget."}`,
      `QuickBooks: ${qb ? `[${qb.status}] ${formatWidgetMetrics(qb)}` : "No QuickBooks widget."}`,
      `SoftDent: ${sd ? `[${sd.status}] ${formatWidgetMetrics(sd)}` : "No SoftDent widget."}`,
      `A/R: ${ar ? `[${ar.status}] ${formatWidgetMetrics(ar)}` : "No A/R widget."}`,
      `Claims: ${claims ? `[${claims.status}] ${formatWidgetMetrics(claims)}` : "No claims widget."}`,
      `Snapshot: ${snapshot?.label || "local snapshot"} at ${snapshot?.gatheredAt || feed?.generatedAt || "—"}`,
      "",
      "Recommendations:",
      recommendations.map((r, i) => `${i + 1}. ${r}`).join("\n"),
    ].join("\n");
  }

  function formatAccountingReviewQueue(feed, snapshot) {
    const widgets = (feed && feed.widgets) || {};
    const keys = ["quickbooksProfitLossDetail", "ebitdaNormalization", "accountsPayableAutomation", "documentIntakeQueue", "documentPreview", "periodCloseAndPosting", "journalPostingQueue"];
    const lines = ["Accounting review queue:", ""];
    keys.forEach((key) => {
      const widget = widgets[key];
      if (!widget) return;
      lines.push(`- [${widget.status}] ${widget.title}: ${formatWidgetMetrics(widget)}`);
      const missing = widgetMissingMetrics(widget);
      if (missing.length) lines.push(`  Review needed: ${missing.join(", ")}.`);
    });
    const docs = snapshot && snapshot.documents;
    if (docs && docs.queueCount) {
      lines.push("", `Document intake queue: ${docs.queueCount} item(s) ready for accounting/Excel review.`);
      if (docs.sourceCounts) {
        lines.push(
          `  Sources: QuickBooks ${docs.sourceCounts.quickbooks || 0}, SoftDent ${docs.sourceCounts.softdent || 0}, OCR ${docs.sourceCounts.ocr || 0}, manual ${docs.sourceCounts.manual || 0}`,
        );
      }
      (docs.top || []).slice(0, 5).forEach((doc) => {
        const source = doc.sourceSystem ? ` · ${doc.sourceSystem}` : "";
        lines.push(`  - ${doc.id || "DOC"} | ${doc.vendor || "Vendor"} | ${doc.amount || "—"} | ${doc.status || "Pending Review"}${source}`);
      });
    }
    lines.push("", "Keep all posting decisions in human review. HAL may draft notes and Excel-style workbooks but cannot post to QuickBooks.");
    lines.push(
      "",
      "Accounting basis note: QuickBooks revenue reflects cash-basis deposits; SoftDent production reflects date-of-service billing. Reconcile collections to QB revenue — not production.",
    );
    return lines.join("\n");
  }

  function formatAccountingReconciliationChecklist(feed, snapshot) {
    const widgets = (feed && feed.widgets) || {};
    const fin = widgets.practiceFinancialOverview;
    const ar = widgets.softdentArAging;
    const qb = snapshot?.dashboards?.quickbooks || {};
    const finDash = snapshot?.dashboards?.financial || {};
    const arCross = finDash.arCrossCheck || {};
    const period = finDash.periodAlignment?.softdentPeriod || finDash.periodAlignment?.quickbooksPeriod || "current period";
    const periodLines = [
      `Current period focus: ${period}`,
      fin ? `Financial overview: [${fin.status}] ${formatWidgetMetrics(fin)}` : "Financial overview: not available.",
      ar ? `SoftDent A/R: [${ar.status}] ${formatWidgetMetrics(ar)}` : "SoftDent A/R: not available.",
      qb.expenses != null ? `QuickBooks monthly expenses (latest import): ${qb.expenses}` : "QuickBooks monthly expenses: not loaded.",
      qb.expenseCategories?.scopeLabel ? `Expense category pivot scope: ${qb.expenseCategories.scopeLabel}` : "Expense category pivot scope: unlabeled export.",
      arCross.comparable
        ? `A/R cross-check: SoftDent $${Number(arCross.softdentTotal || 0).toLocaleString()} vs QuickBooks $${Number(arCross.quickbooksTotal || 0).toLocaleString()} · variance $${Number(arCross.variance || 0).toFixed(2)}${arCross.withinTolerance ? " (within $500 tolerance)" : " (review required)"}`
        : arCross.softdentTotal != null
          ? `A/R cross-check: ${arCross.message}`
          : "A/R cross-check: SoftDent A/R export not loaded.",
      finDash.collectionRateMetrics?.trailingRate
        ? `Trailing collection rate: ${finDash.collectionRateMetrics.trailingRate} (${finDash.collectionRateMetrics.trailingPeriods})`
        : null,
      finDash.collectionRateMetrics?.latestMonthIncomplete
        ? `Latest month ${finDash.collectionRateMetrics.latestMonthPeriod}: ${finDash.collectionRateMetrics.latestMonthRate} — incomplete, excluded from trailing rate`
        : null,
    ].filter(Boolean);
    const lines = [
      "SoftDent + QuickBooks reconciliation checklist (local read-only):",
      "",
      "Industry context: SoftDent has no native QuickBooks sync. Monthly reconciliation compares PMS collections to QB deposits — not production to revenue.",
      "",
      ...periodLines,
      "",
      "Staff steps:",
      "1. SoftDent → Reports → Collection Reports → Reconciliation Report for the prior month; confirm bank deposits match.",
      "2. SoftDent → run a final daysheet for each day in the current month before trusting collections totals.",
      "3. Compare SoftDent collections (not production) to QuickBooks bank deposits / revenue for the same period.",
      "4. Compare SoftDent A/R aging total to QuickBooks balance-sheet A/R (export quickbooks_ar.csv to app_data/nr2/document_inbox/quickbooks/).",
      "5. In NR2, run Work document workbook and review Tab 4 exceptions before period close.",
      "6. Investigate any $0 collections with production > 0 — usually incomplete daysheet export, not a true 0% rate.",
      "",
      "NR2 validation status:",
      `Accounting/excel validation: ${feed.accountingExcelValidation?.status || "UNKNOWN"}`,
    ];
    if (feed.accountingExcelValidation?.issues?.length) {
      feed.accountingExcelValidation.issues.slice(0, 6).forEach((issue) => {
        lines.push(`- [${issue.severity}] ${issue.widgetKey}: ${issue.message}`);
      });
    } else {
      lines.push("- No active accounting validation exceptions.");
    }
    lines.push("", "Posting to QuickBooks remains human-reviewed only.");
    return lines.join("\n");
  }

  function formatDocumentExcelWorkbook(feed, snapshot) {
    const widgets = (feed && feed.widgets) || {};
    const docs = (snapshot && snapshot.documents) || {};
    const qb = (snapshot && snapshot.dashboards && snapshot.dashboards.quickbooks) || {};
    const allRows = docs.workbookSample || docs.top || [];
    const queueBySource = { softdent: [], quickbooks: [], ocr: [], manual: [] };
    allRows.forEach((doc) => {
      const key = documentQueueSourceKey(doc);
      if (queueBySource[key]) queueBySource[key].push(doc);
    });
    const queue = allRows;
    const docTotal = queue.reduce((acc, doc) => acc + (parseMetricNumber(doc.amount) || 0), 0);
    const monthlyRevenue = qb.monthlyRevenue;
    const monthlyExpenses = qb.monthlyExpenses;
    const lines = [
      "Accounting document workbook (Excel-style, local review only):",
      "",
      "Tab 1 — Document Intake Queue (by source system)",
      `Rows: ${docs.queueCount || queue.length || 0}`,
      "SoftDent rows = practice ops. QuickBooks rows = accounting. OCR/manual = scanned or staff-added documents.",
    ];
    if (!queue.length) {
      lines.push("- No documents in queue. Drop files in app_data/nr2/document_inbox or use Add document.");
    } else {
      const renderSourceBlock = (title, rows) => {
        if (!rows.length) return;
        lines.push("", `${title} (${rows.length} visible in sample)`);
        lines.push("Columns: ID | Vendor | Type | Date | Amount | Status | Age (days)");
        rows.slice(0, 8).forEach((doc) => {
          lines.push(
            `- ${doc.id || "DOC"} | ${doc.vendor || "—"} | ${doc.type || "—"} | ${doc.date || "—"} | ${doc.amount || "—"} | ${doc.status || "Pending Review"} | ${doc.age != null ? doc.age : "—"}`,
          );
        });
      };
      renderSourceBlock("SoftDent document imports", queueBySource.softdent);
      renderSourceBlock("QuickBooks document imports", queueBySource.quickbooks);
      renderSourceBlock("OCR inbox documents", queueBySource.ocr);
      renderSourceBlock("Manual documents", queueBySource.manual);
      lines.push(`Queue total (visible rows): ${docTotal ? `$${docTotal.toFixed(2)}` : "—"}`);
    }
    lines.push("", "Tab 2 — QuickBooks Monthly P&L");
    if (monthlyRevenue && monthlyExpenses && monthlyRevenue.labels && monthlyExpenses.labels) {
      const periods = monthlyRevenue.labels;
      periods.forEach((label, index) => {
        const revenue = monthlyRevenue.values[index];
        const expense = monthlyExpenses.values[index];
        const net = revenue != null && expense != null ? revenue - expense : null;
        lines.push(`- ${label}: revenue $${Number(revenue || 0).toLocaleString()} | expenses $${Number(expense || 0).toLocaleString()} | net ${net != null ? `$${net.toLocaleString()}` : "—"}`);
      });
      lines.push("", "Import cache policy: current + prior month only; cache purges after 7 days so totals do not stack.");
    } else {
      lines.push("- Monthly QuickBooks series not available yet. Refresh imports after monthly P&L export fills.");
      const qbWidget = widgets.quickbooksProfitLossDetail;
      if (qbWidget) lines.push(`- Current P&L widget: [${qbWidget.status}] ${formatWidgetMetrics(qbWidget)}`);
    }
    lines.push("", "Tab 3 — Expense Category Pivot");
    const ebitda = widgets.ebitdaNormalization;
    if (ebitda && ebitda.metrics) {
      if (ebitda.metrics.expenseCategoriesScope) lines.push(`- Scope: ${ebitda.metrics.expenseCategoriesScope}`);
      if (ebitda.metrics.expenseCategoriesTotal) lines.push(`- Category pivot total: ${ebitda.metrics.expenseCategoriesTotal}`);
      if (ebitda.metrics.monthlyExpensesLatest) lines.push(`- Monthly P&L expenses (compare here): ${ebitda.metrics.monthlyExpensesLatest}`);
      if (ebitda.metrics.topAddBackCategory) lines.push(`- Top add-back category: ${ebitda.metrics.topAddBackCategory}`);
      if (ebitda.metrics.addBackTotal) lines.push(`- Add-back total: ${ebitda.metrics.addBackTotal}`);
      if (
        !ebitda.metrics.expenseCategoriesTotal &&
        !ebitda.metrics.topAddBackCategory
      ) {
        lines.push("- Expense category pivot waiting on QuickBooks expense categories import.");
      }
    } else {
      lines.push("- Expense category pivot waiting on QuickBooks expense categories import.");
    }
    lines.push(
      "",
      "Accounting basis note: QB revenue = cash-basis deposits; SoftDent production = date-of-service billing. Reconcile collections to QB revenue.",
    );
    lines.push("", "Tab 4 — Reconciliation & Exceptions");
    lines.push("- Match document vendor/amount to QuickBooks expense categories before posting.");
    lines.push("- Flag documents in Pending Review before period close.");
    if (feed.accountingExcelValidation && feed.accountingExcelValidation.issues && feed.accountingExcelValidation.issues.length) {
      feed.accountingExcelValidation.issues.slice(0, 6).forEach((issue) => {
        lines.push(`- [${issue.severity}] ${issue.widgetKey}: ${issue.message}`);
      });
    } else {
      lines.push("- No accounting/excel validation exceptions on current widget feed.");
    }
    lines.push("", "HAL recommendation: review Tab 1 documents against Tab 2 monthly expenses and Tab 3 categories. Posting remains human-reviewed only.");
    return lines.join("\n");
  }

  function formatExcelReconciliation(feed, snapshot) {
    const widgets = (feed && feed.widgets) || {};
    const docs = snapshot && snapshot.documents;
    return [
      "Excel-style reconciliation plan:",
      "",
      "1. Source tabs: SoftDent dashboard, SoftDent claims, verified SoftDent A/R, QuickBooks monthly P&L, QuickBooks expenses, local accounting documents.",
      "2. Normalize columns: period, source, category, amount, claim status, payer, provider (Dr. Michael Reno), document status.",
      "3. Sort/filter: failed or degraded widgets first, then missing metrics, then oldest/stalest source.",
      "4. Compare: SoftDent production vs collections, QuickBooks revenue vs SoftDent collections, verified A/R vs claims balances, document queue amounts vs QuickBooks expenses.",
      "5. Pivot/group: claims by status, A/R by aging bucket, documents by posting readiness, expenses by add-back category.",
      "6. Exception list: blanks, mismatched periods, missing A/R, missing claim status, missing QuickBooks monthly series, missing document metadata.",
      "",
      `Current financial widget: ${widgets.practiceFinancialOverview ? `[${widgets.practiceFinancialOverview.status}] ${formatWidgetMetrics(widgets.practiceFinancialOverview)}` : "not available"}`,
      `Current A/R widget: ${widgets.arAgingAndCollections ? `[${widgets.arAgingAndCollections.status}] ${formatWidgetMetrics(widgets.arAgingAndCollections)}` : "not available"}`,
      docs && docs.queueCount
        ? `Document intake queue: ${docs.queueCount} document(s) for vendor/amount matching.`
        : "Document intake queue: empty — OCR inbox or Add document needed.",
      "",
      "Ask HAL: work document workbook — for a document-by-document Excel-style review against QuickBooks.",
      "",
      "HAL should recommend from verified values only and leave unknowns blank.",
    ].join("\n");
  }

  function formatWidgetDetail(feed, widgetKey) {
    const w = feed && feed.widgets && feed.widgets[widgetKey];
    if (!w) return "Widget not found in the current feed.";
    const lines = [
      `${w.title} [${w.status}]`,
      w.summary,
      "",
      formatWidgetMetrics(w),
      "",
      `Related page: ${w.navTarget || "—"} · local only · not submitted.`,
    ];
    return lines.join("\n");
  }

  function summarizeWidgetFeed(feed) {
    if (!feed || !feed.widgets) return "";
    return WIDGET_ORDER.map((key) => {
      const w = feed.widgets[key];
      if (!w) return "";
      return `[${w.status}] ${w.title}: ${formatWidgetMetrics(w)}`;
    })
      .filter(Boolean)
      .join("\n");
  }

  return {
    SAFETY_DISCLAIMER,
    // sanitization
    sanitizeText,
    // accounting
    getChartOfAccounts,
    isPeriodOpen,
    inferTransactionType,
    draftJournalEntry,
    buildJournalValidation,
    draftAndValidateJournal,
    draftAndValidateJournalAsync,
    formatJournalDraft,
    // claim packet readiness
    assessClaimReadiness,
    buildClaimReadinessResponse,
    formatClaimReadinessAnswer,
    // office-manager attention
    buildOfficeManagerAttention,
    formatOfficeManagerAttention,
    // HAL sidenotes
    createSideNote,
    applySideNoteUpdate,
    buildSideNoteMonitor,
    formatSideNoteMonitor,
    formatSideNotesList,
    sideNoteFingerprint,
    // office-manager tasks
    createTask,
    findTaskBySourceId,
    upsertHalTask,
    autoResolveHalTasks,
    applyTaskUpdate,
    computeTaskMetrics,
    // knowledge memory
    isMemoryStale,
    isMemoryIndexable,
    filterIndexableMemories,
    memoryContainsForbidden,
    memoryGuidanceText,
    // document RAG / retrieval
    INSUFFICIENT_DOCUMENT_CONTEXT_ANSWER,
    RAG_GUARDRAILS,
    chunkText,
    buildRagIndex,
    queryRag,
    buildDocumentAnswerPrompt,
    answerFromLibrary,
    formatRagResult,
    // softdent read status
    SOFTDENT_MISSING_DATA_CODES,
    softDentReadSourceStatus,
    formatSourceHealthText,
    // widgets
    WIDGET_NAV,
    WIDGET_ORDER,
    WIDGET_FILL_REQUIREMENTS,
    buildWidgetFeed,
    crossReconcileSkill,
    enforceReceivablesArPolicy,
    formatPostingQueueList,
    formatWidgetFeed,
    formatWidgetFillSuggestions,
    formatWidgetMissingData,
    buildWidgetSourceTrace,
    formatWidgetSourceTrace,
    formatWidgetFillPriority,
    formatImportChecklist,
    formatImportHealthSummary,
    formatSourceSystemGuide,
    formatPracticeSourcePullResult,
    buildDraftInsuranceNarrative,
    formatDraftInsuranceNarrativeResult,
    buildSoftdentExtractStatus,
    formatSoftdentExtractStatus,
    resolveClaimById,
    narrativeModelLane,
    formatNarrativeForClaim,
    formatHalJobRequirements,
    formatWidgetPeriodRequirements,
    formatCognitivePathways,
    SOURCE_SYSTEM_PROFILES,
    resolvePracticeSourceRequest,
    formatPracticeSourceCatalog,
    formatPracticeSourceFetch,
    formatDataQualityCheck,
    formatEmptyWidgetExplanation,
    formatDailyOwnerBriefing,
    formatAccountingReviewQueue,
    formatAccountingReconciliationChecklist,
    formatDocumentExcelWorkbook,
    formatExcelReconciliation,
    formatWidgetDetail,
    formatWidgetMetrics,
    summarizeWidgetFeed,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalSkills;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalSkills = HalSkills;
}
if (typeof window !== "undefined") {
  window.HalSkills = HalSkills;
}

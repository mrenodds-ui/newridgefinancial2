/**
 * HAL Skills — client-side port of the legacy HAL backend business logic.
 *
 * Brings the legacy _legacy/app/hal/* Python capabilities into the single
 * frontend program with NO backend: accounting journal drafting + validation +
 * posting queue, claim packet readiness, office-manager attention + tasks,
 * knowledge memory, and PII sanitization.
 *
 * Everything here is local-only and read/draft-only. No external action, no
 * SoftDent/QuickBooks writeback, no submission. The HAL firewall still runs
 * before any model call; these skills never perform external or destructive
 * operations.
 *
 * Browser + Node compatible (no DOM).
 */
const HalSkills = (function () {
  const PROGRAM_SCHEMA_VERSION = "nr2-hal-skill-v1";
  const SAFETY_DISCLAIMER =
    "Local office-manager workflow only. Draft only where applicable. Requires human review. " +
    "Local only. not_submitted. Not written to SoftDent. No email/fax/upload action performed. No external delivery.";

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

  /* ============================================================
   * Accounting — port of accounting_tools.py + accounting_validation.py
   * ========================================================== */

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

  function getChartOfAccounts() {
    return Object.assign({}, CHART_OF_ACCOUNTS);
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
    const coa = chartOfAccounts || CHART_OF_ACCOUNTS;
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
    const validation = buildJournalValidation({ lines, chartOfAccounts: CHART_OF_ACCOUNTS, openPeriod });
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
    };
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
    lines.push("Stays in the posting queue for human review. Nothing posted to the ledger.");
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
          actionHint: "Work local tasks inside this app only. No SoftDent writeback or external delivery.",
          count: openTasks,
        });
      }
    }

    // Honest "no live source" items, mirroring the legacy backend.
    [
      ["treatment-plan-unavailable", "treatment_plan", "Treatment plan follow-up is limited", "No approved treatment-plan export source is available yet.", "missing_treatment_plan_export"],
      ["hygiene-recall-unavailable", "hygiene_recall", "Hygiene and recall follow-up is limited", "No approved recall or hygiene export source is available yet.", "missing_hygiene_recall_export"],
      ["vendor-tracker-local-only", "vendor", "Vendor and software issues are local-only", "Vendor/software issue tracking uses local records in this app only.", "missing_vendor_tracker_source"],
    ].forEach(([id, category, title, detail, code]) => {
      missingCodes.add(code);
      items.push({ itemId: id, category, severity: "info", title, detail, actionHint: "Use local office tasks until a real export source is approved.", missingDataCodes: [code] });
    });

    return {
      meta: skillMeta("office.attention", "officeManager"),
      summary: `${items.length} office-manager attention item(s) are visible. All actions remain local only, not submitted, and not written to SoftDent.`,
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
      taskId: uid("omt"),
      title,
      description: String((req && req.description) || "").trim(),
      category,
      status: "open",
      priority,
      patientLabel: req.patientLabel || req.patient_label || null,
      claimId: req.claimId || req.claim_id || null,
      sourceRefs: (req.sourceRefs || req.source_refs || []).slice(),
      missingDataCodes: (req.missingDataCodes || req.missing_data_codes || []).slice(),
      dueDate: req.dueDate || req.due_date || null,
      assignedTo: req.assignedTo || req.assigned_to || null,
      createdBy: actor,
      createdAt: now,
      updatedAt: now,
      localOnly: true,
      externalActionPerformed: false,
      softdentWritebackPerformed: false,
    };
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
    lines.push("", "Grounded, local-only retrieval. A local model can summarize these with the grounded prompt; nothing was sent externally.");
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
    const claimsAvailable = !!(snap.claims && snap.claims.total > 0);
    const ar = snap.dashboards && snap.dashboards.ar;
    const arAvailable = !!(ar && (ar.buckets || ar.aging || ar.total));
    const missing = [];
    if (!claimsAvailable) missing.push(SOFTDENT_MISSING_DATA_CODES.claims);
    if (!arAvailable) missing.push(SOFTDENT_MISSING_DATA_CODES.ar);
    return {
      meta: skillMeta("softdent.readStatus", "softdent"),
      claimsAvailable,
      clinicalNotesAvailable: false,
      arAvailable,
      missingDataCodes: missing,
      note: "A/R is only reported from a verified source; HAL never fabricates a $0 balance.",
    };
  }

  /* ============================================================
   * Widgets — port of widget_builder.py + widget_feed.py
   * (import-cache widget feed derived from the program snapshot)
   * ========================================================== */

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

  function buildWidgetFeed(snapshot) {
    const snap = snapshot || {};
    const dashboards = snap.dashboards || {};
    const sdStatus = softDentReadSourceStatus(snap);
    const arAvailable = sdStatus.arAvailable;
    const claims = snap.claims || {};

    const financialStatus = dashboards.financial ? "SUCCESS" : "FAILED";
    const qbStatus = dashboards.quickbooks ? (/(blocked|stale)/i.test(String(dashboards.quickbooks.syncStatus || "")) ? "DEGRADED" : "SUCCESS") : "FAILED";
    const softdentStatus = dashboards.softdent ? "SUCCESS" : "FAILED";
    const claimsStatus = claims.total > 0 ? (arAvailable ? "SUCCESS" : "DEGRADED") : "FAILED";
    const careStatus = softdentStatus === "SUCCESS" && !arAvailable ? "DEGRADED" : softdentStatus;
    const pendingPosting = ((snap.documents && snap.documents.posting) || []).reduce(
      (acc, p) => (/pending/i.test(p.label) ? acc + (p.count || 0) : acc),
      0,
    );

    const widgets = {
      practiceFinancialOverview: {
        title: "Practice Financial Overview",
        status: mergeWidgetStatus(qbStatus, softdentStatus),
        summary: "Practice revenue from QuickBooks and production/collections from the SoftDent import cache. Dental A/R is not sourced from QuickBooks.",
        metrics: {
          monthlyRevenue: dashboards.quickbooks ? dashboards.quickbooks.revenue || null : null,
          productionTotal: dashboards.softdent ? dashboards.softdent.production || null : null,
        },
      },
      accountsPayableAutomation: {
        title: "Accounts Payable Automation",
        status: qbStatus,
        summary: "QuickBooks expense totals and posting-queue workflow counts from the import cache.",
        metrics: { expenseTotal: dashboards.quickbooks ? dashboards.quickbooks.expenses || null : null, postingQueuePendingCount: pendingPosting || null },
      },
      smartClaimsAndReceivables: {
        title: "Smart Claims & Receivables",
        status: claimsStatus,
        summary: arAvailable
          ? "SoftDent claims and receivables totals derived from local practice operations data."
          : "SoftDent claims totals from local data; dental A/R is unavailable until an explicit SoftDent A/R export is present.",
        metrics: { outstandingClaimCount: claims.total || null, accountsReceivableTotal: null },
      },
      careDeliveryPerformance: {
        title: "Care Delivery Performance",
        status: careStatus,
        summary: arAvailable
          ? "Practice-wide SoftDent operational balances from the import cache."
          : "Practice-wide SoftDent operational activity from the import cache; patient A/R balances are unavailable until an explicit SoftDent A/R export is present.",
        metrics: { patientBalanceTotal: null },
      },
    };

    const feed = {
      meta: skillMeta("widgets.feed", "programSnapshot"),
      manager: "Import cache",
      runId: uid("run"),
      generatedAt: snap.gatheredAt || new Date().toISOString(),
      widgets,
      sources: {
        quickbooks: { lastStatus: qbStatus, origin: "local" },
        softdent: { lastStatus: softdentStatus, origin: "local" },
      },
      jobs: {},
      localOnly: true,
    };
    const publish = publishJobStatus(widgets);
    feed.jobs = { importCacheRefresh: { status: publish }, widgetPublish: { status: publish } };
    return enforceReceivablesArPolicy(feed, arAvailable);
  }

  // Never present an A/R total when no verified A/R source exists; degrade instead.
  function enforceReceivablesArPolicy(feed, arAvailable) {
    if (arAvailable) return feed;
    [
      ["smartClaimsAndReceivables", ["accountsReceivableTotal"]],
      ["careDeliveryPerformance", ["patientBalanceTotal"]],
    ].forEach(([key, metricKeys]) => {
      const widget = feed.widgets[key];
      if (!widget || !widget.metrics) return;
      metricKeys.forEach((m) => {
        widget.metrics[m] = null;
      });
      if (String(widget.status).toUpperCase() === "SUCCESS") widget.status = "DEGRADED";
    });
    const publish = publishJobStatus(feed.widgets);
    feed.jobs.importCacheRefresh = { status: publish };
    feed.jobs.widgetPublish = { status: publish };
    return feed;
  }

  function formatWidgetFeed(feed) {
    const lines = [`Manager dashboard widgets (${feed.manager}, local only):`, ""];
    Object.values(feed.widgets).forEach((w) => {
      lines.push(`[${w.status}] ${w.title} — ${w.summary}`);
    });
    lines.push("", `Publish job: ${feed.jobs.widgetPublish.status}. Local-only; A/R shown only from a verified source.`);
    return lines.join("\n");
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
    formatJournalDraft,
    // claim packet readiness
    assessClaimReadiness,
    buildClaimReadinessResponse,
    formatClaimReadinessAnswer,
    // office-manager attention
    buildOfficeManagerAttention,
    formatOfficeManagerAttention,
    // office-manager tasks
    createTask,
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
    // widgets
    buildWidgetFeed,
    enforceReceivablesArPolicy,
    formatWidgetFeed,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalSkills;
}
if (typeof window !== "undefined") {
  window.HalSkills = HalSkills;
}

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
  const SAFETY_DISCLAIMER =
    "Local office-manager workflow only. Draft only where applicable. Requires human review. " +
    "Local only. not_submitted. Not written to SoftDent. No email/fax/upload action performed. No external delivery.";

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
      { account_code: "1310", account_name: "Prepaid Insurance", debit: "amount", credit: 0 },
      { account_code: "1010", account_name: "Cash", debit: 0, credit: "amount" },
    ],
    depreciation: [
      { account_code: "6100", account_name: "Depreciation Expense", debit: "amount", credit: 0 },
      { account_code: "1590", account_name: "Accumulated Depreciation", debit: 0, credit: "amount" },
    ],
    patient_cash_receipt: [
      { account_code: "1010", account_name: "Cash", debit: "amount", credit: 0 },
      { account_code: "1100", account_name: "Accounts Receivable", debit: 0, credit: "amount" },
    ],
    equipment_purchase: [
      { account_code: "1500", account_name: "Equipment", debit: "amount", credit: 0 },
      { account_code: "1010", account_name: "Cash", debit: 0, credit: "amount" },
    ],
    vendor_bill: [
      { account_code: "5200", account_name: "Dental Supplies Expense", debit: "amount", credit: 0 },
      { account_code: "2100", account_name: "Accounts Payable", debit: 0, credit: "amount" },
    ],
    payroll_accrual: [
      { account_code: "6200", account_name: "Payroll Expense", debit: "amount", credit: 0 },
      { account_code: "2200", account_name: "Accrued Expenses", debit: 0, credit: "amount" },
    ],
    supplies_accrual: [
      { account_code: "5200", account_name: "Dental Supplies Expense", debit: "amount", credit: 0 },
      { account_code: "2200", account_name: "Accrued Expenses", debit: 0, credit: "amount" },
    ],
    patient_service_revenue: [
      { account_code: "1100", account_name: "Accounts Receivable", debit: "amount", credit: 0 },
      { account_code: "4000", account_name: "Patient Service Revenue", debit: 0, credit: "amount" },
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
      account_code: line.account_code,
      account_name: line.account_name,
      debit: round2(line.debit === "amount" ? amount : line.debit),
      credit: round2(line.credit === "amount" ? amount : line.credit),
      memo: description,
      transaction_type: type,
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
      .map((line) => String(line.account_code || ""))
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
      debit_total: debitTotal,
      credit_total: creditTotal,
      open_period: openPeriod,
      account_validation_passed: missingAccounts.length === 0,
      amount_validation_passed: !hasNegative && invalidAmountFields.length === 0,
      issues,
    };
  }

  function draftAndValidateJournal(opts) {
    const { description, period, amount, context } = opts || {};
    const lines = draftJournalEntry({ description, amount, context });
    const openPeriod = isPeriodOpen(period);
    const validation = buildJournalValidation({ lines, chartOfAccounts: CHART_OF_ACCOUNTS, openPeriod });
    return {
      description,
      period,
      amount,
      transaction_type: lines[0] ? lines[0].transaction_type : "patient_service_revenue",
      lines,
      validation,
      draft_status: "draft_only",
      posting_status: "pending_review",
      safety: { local_only: true, not_submitted: true, human_review_required: true, posted_to_ledger: false },
    };
  }

  function formatJournalDraft(draft) {
    const lines = [
      `Journal draft (local · draft only · not posted) — ${draft.transaction_type.replace(/_/g, " ")}:`,
      `Period ${draft.period} · ${draft.validation.open_period ? "OPEN" : "CLOSED"}`,
    ];
    draft.lines.forEach((l) => {
      const dr = l.debit ? `Dr ${l.debit.toFixed(2)}` : "";
      const cr = l.credit ? `Cr ${l.credit.toFixed(2)}` : "";
      lines.push(`  ${l.account_code} ${l.account_name}: ${dr}${cr}`);
    });
    lines.push(`Balanced: ${draft.validation.balanced ? "yes" : "no"} (Dr ${draft.validation.debit_total} / Cr ${draft.validation.credit_total})`);
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
      packet_id: `cpr-${claim.id || "unknown"}`,
      claim_ref: claim.id || null,
      patient_label: claim.patient || null,
      status: readiness,
      priority,
      blockers: readiness === "blocked" ? missing.slice() : [],
      missing_items: missing,
      recommended_next_actions: Array.from(new Set(actions)),
      can_prepare_local_draft: canPrepareDraft,
      local_draft_status: canPrepareDraft ? "draft_available" : "needs_facts",
      staff_summary: summary,
      safety: { local_only: true, not_submitted: true, human_review_required: true, external_delivery_allowed: false },
    };
  }

  function buildClaimReadinessResponse(claimsList) {
    const items = (claimsList || []).map(assessClaimReadiness);
    return {
      generated_at_utc: new Date().toISOString(),
      summary: {
        ready_count: items.filter((i) => i.status === "ready").length,
        needs_review_count: items.filter((i) => i.status === "needs_review").length,
        blocked_count: items.filter((i) => i.status === "blocked").length,
        total_count: items.length,
      },
      items,
      safety_disclaimer: SAFETY_DISCLAIMER,
      local_only: true,
      submission_status: "not_submitted",
    };
  }

  function formatClaimReadinessAnswer(resp) {
    const s = resp.summary;
    const lines = [
      "Claim packet readiness (local only):",
      `- Ready: ${s.ready_count}`,
      `- Needs review: ${s.needs_review_count}`,
      `- Blocked: ${s.blocked_count}`,
      "",
      "HAL can prepare a local packet and draft. Staff must review before use. Nothing has been submitted or sent.",
    ];
    const examples = resp.items.slice(0, 4);
    if (examples.length) {
      lines.push("", "Examples:");
      examples.forEach((item) => {
        const headline = item.claim_ref ? `${item.claim_ref}: ${item.staff_summary}` : item.staff_summary;
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
          item_id: "claims-denied",
          category: "claims_follow_up",
          severity: denied >= 3 ? "warning" : "info",
          title: "Denied claims need follow-up",
          detail: `${denied} denied claim(s) are visible in the local claims workbench.`,
          action_hint: "Use Claims Workbench to prepare a local review draft. No payer contact.",
          count: denied,
        });
      }
      if (review > 0) {
        items.push({
          item_id: "claims-needs-review",
          category: "claims_follow_up",
          severity: review >= 5 ? "warning" : "info",
          title: "Claims in the Needs Review lane",
          detail: `${review} claim(s) await staff review before any payer-facing step.`,
          action_hint: "Work the Needs Review lane first. Nothing is submitted.",
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
          item_id: "posting-queue-pending",
          category: "revenue",
          severity: "info",
          title: "Accounting posting queue needs review",
          detail: `${pending} local posting-queue item(s) remain pending human review.`,
          action_hint: "Review the accounting posting queue before month-end close.",
          count: pending,
        });
      }
    }

    const qb = snap.dashboards && snap.dashboards.quickbooks;
    if (qb && /blocked|stale|pending/i.test(String(qb.syncStatus || qb.lastSync || ""))) {
      // QuickBooks registry state is Blocked in the program; surface as revenue attention.
      items.push({
        item_id: "quickbooks-source-health",
        category: "revenue",
        severity: "warning",
        title: "QuickBooks source needs attention",
        detail: "QuickBooks sync is not current; expense and revenue totals may be stale.",
        action_hint: "Review revenue inputs before month-end office-manager summaries.",
      });
    }

    if (taskMetrics) {
      const openTasks =
        (taskMetrics.open_count || 0) + (taskMetrics.in_progress_count || 0) + (taskMetrics.blocked_count || 0);
      if (openTasks > 0) {
        items.push({
          item_id: "local-office-tasks-open",
          category: "local_tasks",
          severity: (taskMetrics.urgent_open_count || 0) > 0 ? "warning" : "info",
          title: "Unresolved local office tasks",
          detail: `${openTasks} local office task(s) remain open, in progress, or blocked.`,
          action_hint: "Work local tasks inside this app only. No SoftDent writeback or external delivery.",
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
      items.push({ item_id: id, category, severity: "info", title, detail, action_hint: "Use local office tasks until a real export source is approved.", missing_data_codes: [code] });
    });

    return {
      generated_at_utc: new Date().toISOString(),
      summary: `${items.length} office-manager attention item(s) are visible. All actions remain local only, not submitted, and not written to SoftDent.`,
      safety_disclaimer: SAFETY_DISCLAIMER,
      items,
      missing_data_codes: Array.from(missingCodes).sort(),
      local_only: true,
      submission_status: "not_submitted",
    };
  }

  function formatOfficeManagerAttention(resp) {
    const lines = ["Office-manager attention (local only):", resp.summary, ""];
    resp.items.slice(0, 8).forEach((item) => {
      const sev = item.severity === "critical" ? "[!]" : item.severity === "warning" ? "[*]" : "[i]";
      lines.push(`${sev} ${item.title}${item.count ? ` (${item.count})` : ""} — ${item.detail}`);
    });
    lines.push("", resp.safety_disclaimer);
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
      task_id: uid("omt"),
      title,
      description: String((req && req.description) || "").trim(),
      category,
      status: "open",
      priority,
      patient_label: req.patient_label || null,
      claim_id: req.claim_id || null,
      source_refs: (req.source_refs || []).slice(),
      missing_data_codes: (req.missing_data_codes || []).slice(),
      due_date: req.due_date || null,
      assigned_to: req.assigned_to || null,
      created_by: actor,
      created_at_utc: now,
      updated_at_utc: now,
      local_only: true,
      external_action_performed: false,
      softdent_writeback_performed: false,
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
    ["patient_label", "claim_id", "due_date", "assigned_to"].forEach((field) => {
      if (updates[field] != null) next[field] = updates[field];
    });
    if (updates.source_refs != null) next.source_refs = updates.source_refs.slice();
    if (updates.missing_data_codes != null) next.missing_data_codes = updates.missing_data_codes.slice();
    next.updated_at_utc = new Date().toISOString();
    return next;
  }

  function computeTaskMetrics(tasks) {
    const list = tasks || [];
    const count = (status) => list.filter((t) => t.status === status).length;
    return {
      open_count: count("open"),
      in_progress_count: count("in_progress"),
      blocked_count: count("blocked"),
      completed_count: count("completed"),
      dismissed_count: count("dismissed"),
      urgent_open_count: list.filter((t) => t.status === "open" && t.priority === "urgent").length,
      local_only: true,
      external_action_performed: false,
      softdent_writeback_performed: false,
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
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalSkills;
}
if (typeof window !== "undefined") {
  window.HalSkills = HalSkills;
}

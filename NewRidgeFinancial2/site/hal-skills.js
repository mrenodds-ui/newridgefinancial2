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
    "Local office-manager workflow only. Draft only where applicable. Requires human review. " +
    "Local only. not_submitted. HAL reads SoftDent and QuickBooks only. No posting, writes, email/fax/upload, or external delivery.";

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
        lines.push(`- [${n.status}/${n.priority}] ${n.text.slice(0, 160)}${tagStr}`);
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
        lines.push(`- [${n.status}] (${n.priority}) ${n.text}`);
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
    const arAvailable = !!(
      ar &&
      ((Array.isArray(ar.buckets) && ar.buckets.length) ||
        (Array.isArray(ar.aging) && ar.aging.length) ||
        ar.total)
    );
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

  const WIDGET_NAV = {
    practiceFinancialOverview: "financial",
    financialProductionTrend: "financial",
    payerMixAndCollections: "financial",
    providerPerformance: "financial",
    dataFreshnessQuality: "financial",
    ebitdaNormalization: "financial",
    quickbooksProfitLossDetail: "quickbooks",
    quickbooksSyncHealth: "quickbooks",
    accountsPayableAutomation: "documents",
    documentIntakeQueue: "documents",
    documentPreview: "documents",
    periodCloseAndPosting: "documents",
    smartClaimsAndReceivables: "claims",
    claimsPipeline: "claims",
    claimReadinessAndSafety: "claims",
    careDeliveryPerformance: "softdent",
    softdentArAging: "softdent",
    softdentResponsibility: "softdent",
    softdentSourceHealth: "softdent",
    softdentExportHistory: "softdent",
    arAgingAndCollections: "ar",
    arOutstandingClaims: "ar",
    narrativeWorkflow: "narratives",
    documentLibrary: "library",
  };

  const WIDGET_ORDER = [
    "practiceFinancialOverview",
    "financialProductionTrend",
    "payerMixAndCollections",
    "providerPerformance",
    "dataFreshnessQuality",
    "ebitdaNormalization",
    "quickbooksProfitLossDetail",
    "quickbooksSyncHealth",
    "accountsPayableAutomation",
    "documentIntakeQueue",
    "documentPreview",
    "periodCloseAndPosting",
    "smartClaimsAndReceivables",
    "claimsPipeline",
    "claimReadinessAndSafety",
    "arAgingAndCollections",
    "arOutstandingClaims",
    "careDeliveryPerformance",
    "softdentArAging",
    "softdentResponsibility",
    "softdentSourceHealth",
    "softdentExportHistory",
    "narrativeWorkflow",
    "documentLibrary",
  ];

  const WIDGET_FILL_REQUIREMENTS = {
    practiceFinancialOverview: ["SoftDent dashboard export with production/collections", "QuickBooks revenue/P&L export"],
    financialProductionTrend: ["SoftDent dashboard export with current period production", "Period labels for trend comparison"],
    payerMixAndCollections: ["SoftDent collections and payer mix fields", "Verified collection-rate source"],
    providerPerformance: ["SoftDent dashboard export for Dr. Michael Reno"],
    dataFreshnessQuality: ["Current SoftDent export timestamps", "Current QuickBooks export timestamps"],
    ebitdaNormalization: ["QuickBooks expenses export", "Staff-reviewed EBITDA add-back categories"],
    quickbooksProfitLossDetail: ["QuickBooks revenue/P&L export", "QuickBooks expenses export"],
    quickbooksSyncHealth: ["QuickBooks import files copied into the canonical import folder"],
    accountsPayableAutomation: ["Local accounting document queue", "QuickBooks expenses or vendor document imports"],
    documentIntakeQueue: ["Local accounting documents added to the document queue"],
    documentPreview: ["Selected local document metadata and extracted fields"],
    periodCloseAndPosting: ["Accounting document period assignment", "Human-reviewed posting readiness"],
    smartClaimsAndReceivables: ["SoftDent claims export", "Verified SoftDent A/R export"],
    claimsPipeline: ["SoftDent claims export with claim status values"],
    claimReadinessAndSafety: ["SoftDent claims export", "Local claim readiness checks"],
    arAgingAndCollections: ["Verified SoftDent A/R aging export"],
    arOutstandingClaims: ["SoftDent claims export with balances or verified A/R export"],
    careDeliveryPerformance: ["SoftDent dashboard export", "Verified patient balance/A/R source"],
    softdentArAging: ["Verified SoftDent A/R aging export"],
    softdentResponsibility: ["SoftDent dashboard export with insurance and patient responsibility values"],
    softdentSourceHealth: ["SoftDent dashboard, claims, clinical notes, and optional A/R export files"],
    softdentExportHistory: ["SoftDent export files in the canonical import folder"],
    narrativeWorkflow: ["Local narrative drafts or claim source facts from SoftDent claims"],
    documentLibrary: ["Local library documents or indexed document metadata"],
  };

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
    const financialStatus = dashHasData(dashboards.financial) ? "SUCCESS" : "FAILED";
    const qbStatus = dashHasData(dashboards.quickbooks)
      ? (/(blocked|stale)/i.test(String(dashboards.quickbooks.syncStatus || "")) ? "DEGRADED" : "SUCCESS")
      : "FAILED";
    const softdentStatus = dashHasData(dashboards.softdent) ? "SUCCESS" : "FAILED";
    const claimsStatus = claims.total > 0 ? (arAvailable ? "SUCCESS" : "DEGRADED") : "FAILED";
    const careStatus = softdentStatus === "SUCCESS" && !arAvailable ? "DEGRADED" : softdentStatus;
    const pendingPosting = ((snap.documents && snap.documents.posting) || []).reduce(
      (acc, p) => (/pending/i.test(p.label) ? acc + (p.count || 0) : acc),
      0,
    );
    const fin = dashboards.financial || {};
    const sd = dashboards.softdent || {};
    const qb = dashboards.quickbooks || {};
    const arDash = dashboards.ar || {};
    const docs = snap.documents || {};
    const claimsSnap = snap.claims || {};
    const narratives = snap.narratives || {};
    const library = snap.library || {};
    const monthlyRevenue = metricValue(qb.revenue || plAmount(qb, "Revenue") || fin.productionMtd?.value);
    const monthlyNetIncome = metricValue(plAmount(qb, "Net Income"));
    const expenseTotal = metricValue(qb.expenses || plAmount(qb, "Expenses"));
    const productionTotal = metricValue(sd.production || glanceValue(sd, "Production MTD") || fin.productionMtd?.value);
    const collectionsTotal = metricValue(sd.collections || glanceValue(sd, "Collections MTD"));
    const accountsReceivableTotal = metricValue(arDash.kpis?.[0]?.value || sd.hero?.value);
    const patientBalanceTotal = metricValue(arDash.kpis?.[0]?.value || sd.hero?.value);
    const arStatus = arDash.kpis ? (arAvailable ? "SUCCESS" : "DEGRADED") : "FAILED";
    const docsStatus = docs.period || docs.queueCount ? "SUCCESS" : "FAILED";
    const claimsReadinessStatus =
      !claimsSnap.readiness && !claimsSnap.total ? "FAILED" : claimsSnap.total > 0 ? "SUCCESS" : "DEGRADED";
    const narrativeStatus = snap.narratives ? "SUCCESS" : "FAILED";
    const libraryStatus = snap.library ? "SUCCESS" : "FAILED";

    const widgets = {
      practiceFinancialOverview: {
        key: "practiceFinancialOverview",
        title: "Practice Financial Overview",
        status: mergeWidgetStatus(qbStatus, softdentStatus),
        summary: "Practice revenue from QuickBooks and production/collections from the SoftDent import cache. Dental A/R is not sourced from QuickBooks.",
        navTarget: WIDGET_NAV.practiceFinancialOverview,
        metrics: {
          monthlyRevenue,
          monthlyNetIncome,
          productionTotal,
          collectionsTotal,
        },
      },
      financialProductionTrend: {
        key: "financialProductionTrend",
        title: "Production Trend & YTD",
        status: financialStatus,
        summary: "Production trend and year-to-date production/collections indicators from the financial dashboard cache.",
        navTarget: WIDGET_NAV.financialProductionTrend,
        metrics: {
          productionMtd: metricValue(fin.productionMtd?.value),
          productionTrendLatest: lastSeriesValue(fin.productionTrend?.production),
          ytdProduction: metricValue((fin.productionTrend?.ytd || []).find((m) => m.label === "YTD Production")?.value),
          ytdCollectionRate: metricValue((fin.productionTrend?.ytd || []).find((m) => m.label === "YTD Collection Rate")?.value),
        },
      },
      payerMixAndCollections: {
        key: "payerMixAndCollections",
        title: "Payer Mix & Collections",
        status: financialStatus,
        summary: "Payer mix, collection rate, and top payer share from the owner financial dashboard.",
        navTarget: WIDGET_NAV.payerMixAndCollections,
        metrics: {
          payerMixTotal: metricValue(fin.payerMix?.total),
          collectionRate: metricValue(fin.payerMix?.rate || (fin.metrics || []).find((m) => m.subLabel === "Collection Rate")?.subValue),
          topPayer: metricValue(firstItem(fin.payerMix?.slices)?.label),
          topPayerShare: metricValue(firstItem(fin.payerMix?.slices)?.pct != null ? `${firstItem(fin.payerMix?.slices).pct}%` : null),
        },
      },
      providerPerformance: {
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
      dataFreshnessQuality: {
        key: "dataFreshnessQuality",
        title: "Data Freshness & Quality",
        status: financialStatus,
        summary: "Source freshness and dashboard quality score for the financial program inputs.",
        navTarget: WIDGET_NAV.dataFreshnessQuality,
        metrics: {
          qualityScore: metricValue(fin.quality?.score != null ? `${fin.quality.score}%` : null),
          syncedSources: healthyCount(fin.freshness),
          delayedSource: metricValue((fin.freshness || []).find((f) => /delay|stale|error/i.test(String(f.status || "")))?.system),
          refreshedAt: metricValue(fin.footer?.refreshed),
        },
      },
      ebitdaNormalization: {
        key: "ebitdaNormalization",
        title: "EBITDA Normalization",
        status: mergeWidgetStatus(qbStatus, financialStatus),
        summary: "Potential EBITDA add-backs and expense-category totals from the financial and QuickBooks import cache.",
        navTarget: WIDGET_NAV.ebitdaNormalization,
        metrics: {
          ebitdaAddBackTotal: metricValue(qb.ebitdaTotal),
          ebitdaCandidateCount: metricValue((qb.ebitdaCandidates || []).length || null),
          expenseCategoriesTotal: metricValue(qb.expenseCategories?.total),
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
      quickbooksSyncHealth: {
        key: "quickbooksSyncHealth",
        title: "QuickBooks Sync Health",
        status: qbStatus,
        summary: "QuickBooks connection status, last sync, and trailing expense trend from the import cache.",
        navTarget: WIDGET_NAV.quickbooksSyncHealth,
        metrics: {
          syncStatus: metricValue(qb.syncStatus || qb.sync?.status),
          lastSync: metricValue(qb.lastSync || qb.sync?.lastSync),
          monthlyExpensesLatest: lastSeriesValue(qb.monthlyExpenses),
          netIncomeYtd: monthlyNetIncome,
        },
      },
      accountsPayableAutomation: {
        key: "accountsPayableAutomation",
        title: "Accounts Payable Automation",
        status: qbStatus,
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
        summary: "Document intake queue status counts and oldest visible item from the accounting documents cache.",
        navTarget: WIDGET_NAV.documentIntakeQueue,
        metrics: {
          queueCount: metricValue(docs.queueCount),
          pendingReviewCount: metricValue((docs.posting || []).find((p) => /pending/i.test(p.label))?.count),
          readyToPostCount: metricValue((docs.posting || []).find((p) => /ready/i.test(p.label))?.count),
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
          pendingAmount: metricValue(docs.period?.pending),
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
      claimReadinessAndSafety: {
        key: "claimReadinessAndSafety",
        title: "Claim Readiness & Safety",
        status: claimsReadinessStatus,
        summary: "Claim packet readiness score and local safety posture from the claims workbench cache. Submission remains locked.",
        navTarget: WIDGET_NAV.claimReadinessAndSafety,
        metrics: {
          readinessOverall: metricValue(claimsSnap.readiness?.overall || kpiValue(claimsSnap.kpis, "Claim Readiness")),
          safetyPosture: metricValue(claimsSnap.safety),
          needsReviewCount: metricValue(claimsSnap.byStatus?.["Needs Review"] || claimsSnap.laneTotals?.["Needs Review"]),
          deniedCount: metricValue(claimsSnap.byStatus?.Denied || claimsSnap.laneTotals?.Denied),
        },
      },
      arAgingAndCollections: {
        key: "arAgingAndCollections",
        title: "A/R Aging & Collections",
        status: arStatus,
        summary: arAvailable
          ? "A/R aging buckets, collections trend, and follow-up queue counts from the A/R dashboard cache."
          : "A/R dashboard cache is present but verified dental A/R totals are unavailable until an explicit SoftDent A/R export is present.",
        navTarget: WIDGET_NAV.arAgingAndCollections,
        metrics: {
          totalOutstanding: metricValue(kpiValue(arDash.kpis, "Total Outstanding")),
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
      softdentSourceHealth: {
        key: "softdentSourceHealth",
        title: "SoftDent Source Health",
        status: softdentStatus,
        summary: "SoftDent connection, data freshness, daysheet load, and scheduled export health.",
        navTarget: WIDGET_NAV.softdentSourceHealth,
        metrics: {
          healthyChecks: healthyCount(sd.health),
          totalChecks: metricValue((sd.health || []).length || null),
          connection: metricValue((sd.health || []).find((h) => h.label === "Connection")?.value || sd.status),
          nextExport: metricValue((sd.health || []).find((h) => h.label === "Next Scheduled Export")?.value),
        },
      },
      softdentExportHistory: {
        key: "softdentExportHistory",
        title: "SoftDent Export History",
        status: softdentStatus,
        summary: "Latest SoftDent export jobs, datasets, and record counts from the local import cache.",
        navTarget: WIDGET_NAV.softdentExportHistory,
        metrics: {
          exportCount: metricValue((sd.exports || []).length || null),
          latestExport: metricValue(firstItem(sd.exports)?.name),
          latestStatus: metricValue(firstItem(sd.exports)?.status),
          latestRecords: metricValue(firstItem(sd.exports)?.records),
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
    feed.jobs.importCacheRefresh = { status: publish };
    feed.jobs.widgetPublish = { status: publish };
    return feed;
  }

  function formatWidgetMetricLabel(key) {
    return String(key || "")
      .replace(/([A-Z])/g, " $1")
      .replace(/^./, (c) => c.toUpperCase())
      .trim();
  }

  function formatWidgetMetrics(widget) {
    const metrics = (widget && widget.metrics) || {};
    const pairs = Object.entries(metrics)
      .filter(([, v]) => v !== null && v !== undefined && v !== "")
      .map(([k, v]) => `${formatWidgetMetricLabel(k)}: ${v}`);
    return pairs.length ? pairs.join(" · ") : "No verified metrics in this snapshot.";
  }

  function widgetMissingMetrics(widget) {
    return Object.entries((widget && widget.metrics) || {})
      .filter(([, value]) => value === null || value === undefined || value === "" || value === "—")
      .map(([key]) => formatWidgetMetricLabel(key));
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
      "softdentSourceHealth",
      "quickbooksSyncHealth",
      "practiceFinancialOverview",
      "quickbooksProfitLossDetail",
      "dataFreshnessQuality",
      "arAgingAndCollections",
      "smartClaimsAndReceivables",
      "claimsPipeline",
      "claimReadinessAndSafety",
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
      "narrativeWorkflow",
      "documentLibrary",
      "softdentExportHistory",
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
    lines.push("", "Rationale: source health first, then owner financials, A/R and claims, then accounting documents, narratives, and library context.");
    return lines.join("\n");
  }

  function formatImportChecklist(feed) {
    const qbStatus = feed?.sources?.quickbooks?.lastStatus || "UNKNOWN";
    const sdStatus = feed?.sources?.softdent?.lastStatus || "UNKNOWN";
    return [
      "Import checklist to fill widgets:",
      "",
      `1. SoftDent dashboard export -> app/data/imports/softdent/ (current status: ${sdStatus})`,
      "   Fills: production, collections, provider performance for Dr. Michael Reno, responsibility split, SoftDent source health.",
      "2. SoftDent claims export -> app/data/imports/softdent/",
      "   Fills: claims pipeline, claim readiness, outstanding claims, narrative source facts.",
      "3. Verified SoftDent A/R aging export -> app/data/imports/softdent/",
      "   Fills: A/R aging, receivables, patient/insurance balances. HAL will not fabricate A/R.",
      `4. QuickBooks revenue/P&L export -> app/data/imports/quickbooks/ (current status: ${qbStatus})`,
      "   Fills: practice financial overview, P&L detail, revenue, net income.",
      "5. QuickBooks expenses export -> app/data/imports/quickbooks/",
      "   Fills: expenses, EBITDA candidates, accounting review queue.",
      "6. Local accounting documents, library files, and narrative drafts.",
      "   Fills: document intake, selected document preview, period close, narrative workflow, document library.",
      "",
      "After copying files, ask HAL: refresh imports. HAL reads only; nothing is written back.",
    ].join("\n");
  }

  function formatDataQualityCheck(feed) {
    if (!feed || !feed.widgets) return "No widget feed is available yet. Refresh imports, then ask again.";
    const failed = WIDGET_ORDER.map((key) => feed.widgets[key]).filter((w) => w && String(w.status).toUpperCase() === "FAILED");
    const degraded = WIDGET_ORDER.map((key) => feed.widgets[key]).filter((w) => w && String(w.status).toUpperCase() === "DEGRADED");
    const lines = [
      "Data quality check before recommendations:",
      "",
      `Widget publish status: ${feed.jobs?.widgetPublish?.status || "UNKNOWN"}`,
      `Failed widgets: ${failed.length}`,
      `Degraded widgets: ${degraded.length}`,
      "",
      "Checks HAL should perform:",
      "1. Confirm SoftDent and QuickBooks import freshness before using totals.",
      "2. Leave A/R blank unless a verified SoftDent A/R export exists.",
      "3. Confirm provider performance is only Dr. Michael Reno.",
      "4. Compare SoftDent production/collections to QuickBooks revenue only as a review signal, not as proof they must match.",
      "5. Flag blanks, conflicting periods, missing claim statuses, and missing document metadata before recommendations.",
    ];
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
    const qb = widgets.quickbooksSyncHealth;
    const sd = widgets.softdentSourceHealth;
    const recommendations = [
      "Refresh imports first if source health is degraded or failed.",
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

  function formatAccountingReviewQueue(feed) {
    const widgets = (feed && feed.widgets) || {};
    const keys = ["quickbooksSyncHealth", "quickbooksProfitLossDetail", "ebitdaNormalization", "accountsPayableAutomation", "documentIntakeQueue", "documentPreview", "periodCloseAndPosting"];
    const lines = ["Accounting review queue:", ""];
    keys.forEach((key) => {
      const widget = widgets[key];
      if (!widget) return;
      lines.push(`- [${widget.status}] ${widget.title}: ${formatWidgetMetrics(widget)}`);
      const missing = widgetMissingMetrics(widget);
      if (missing.length) lines.push(`  Review needed: ${missing.join(", ")}.`);
    });
    lines.push("", "Keep all posting decisions in human review. HAL may draft notes but cannot post to QuickBooks.");
    return lines.join("\n");
  }

  function formatExcelReconciliation(feed) {
    const widgets = (feed && feed.widgets) || {};
    return [
      "Excel-style reconciliation plan:",
      "",
      "1. Source tabs: SoftDent dashboard, SoftDent claims, verified SoftDent A/R, QuickBooks P&L, QuickBooks expenses, local documents.",
      "2. Normalize columns: period, source, category, amount, claim status, payer, provider (Dr. Michael Reno), document status.",
      "3. Sort/filter: failed or degraded widgets first, then missing metrics, then oldest/stalest source.",
      "4. Compare: SoftDent production vs collections, QuickBooks revenue vs SoftDent collections, verified A/R vs claims balances, expenses vs documents.",
      "5. Pivot/group: claims by status, A/R by aging bucket, documents by posting readiness, expenses by add-back category.",
      "6. Exception list: blanks, mismatched periods, missing A/R, missing claim status, missing QuickBooks expense file, missing document metadata.",
      "",
      `Current financial widget: ${widgets.practiceFinancialOverview ? `[${widgets.practiceFinancialOverview.status}] ${formatWidgetMetrics(widgets.practiceFinancialOverview)}` : "not available"}`,
      `Current A/R widget: ${widgets.arAgingAndCollections ? `[${widgets.arAgingAndCollections.status}] ${formatWidgetMetrics(widgets.arAgingAndCollections)}` : "not available"}`,
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
    WIDGET_NAV,
    WIDGET_ORDER,
    buildWidgetFeed,
    enforceReceivablesArPolicy,
    formatWidgetFeed,
    formatWidgetFillSuggestions,
    formatWidgetMissingData,
    formatWidgetFillPriority,
    formatImportChecklist,
    formatDataQualityCheck,
    formatEmptyWidgetExplanation,
    formatDailyOwnerBriefing,
    formatAccountingReviewQueue,
    formatExcelReconciliation,
    formatWidgetDetail,
    formatWidgetMetrics,
    summarizeWidgetFeed,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalSkills;
}
if (typeof window !== "undefined") {
  window.HalSkills = HalSkills;
}

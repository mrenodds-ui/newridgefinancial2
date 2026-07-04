/**
 * HAL agent programming — Cursor Auto-style response contract.
 * Loaded before hal-core.js; every model lane and polish path should honor this.
 */
(function (global) {
  "use strict";

  const VERSION = "auto-agent-v10";

  const CONTRACT_LINES = [
    "PROGRAMMING: You are HAL, programmed like Cursor Auto — a capable agent colleague, not a chatbot narrator.",
    "",
    "Agent loop (internal — never expose chain-of-thought):",
    "1) Read the question, thread, and current page context before writing.",
    "2) Gather local evidence via tools when available — tools may run in parallel or auto-prefetch (snapshot, widgets, imports, grep, files).",
    "3) Answer directly, cite sources, name gaps, recommend one safe next step.",
    "4) Self-check: no invented numbers, no external actions claimed, no filler.",
    "",
    "Response contract (every reply):",
    "1) Lead with the direct answer in the first sentence — no preamble, no identity monologue.",
    "2) Ground claims in local evidence: registry, imports, tool results, or snapshot — name the source.",
    "3) Explain the operational or accounting implication in plain language staff can act on.",
    "4) State uncertainty plainly: missing imports, stale exports, empty widgets, offline models.",
    "5) End with one safe, specific next step (open a page, refresh imports, run readiness, draft locally).",
    "",
    "Scope and depth (like a coding agent):",
    "- Proportional depth: simple or action questions get a direct 1–3 sentence answer; complex, reasoning, or code questions get five to ten sentences.",
    "- Minimum five sentences only when the question is open-ended, planning, or diagnostic — not for navigation, refresh, or yes/no.",
    "- Stay focused — answer what was asked; do not dump unrelated capability lists or page inventories.",
    "- Use existing program conventions (pages, widgets, imports) — do not invent new workflows.",
    "- Markdown is allowed when discussing program source: **bold**, `inline code`, short bullet lists, and code citations like ```12:15:site/app.js when grep/file tools ran.",
    "- Prose paragraphs by default — use bullets or code blocks only when they improve clarity (source review, steps they asked for).",
    "",
    "Question types:",
    "- Yes/no: start with Yes or No, then explain why with detail.",
    "- Corrections: acknowledge briefly (To clarify —), then restate the accurate answer.",
    "- Follow-ups: use conversation context; do not repeat the prior answer verbatim.",
    "- Plans: only when they ask to prioritize, plan, or reason through — still prose, not bullet dumps.",
    "",
    "Reasoning discipline:",
    "- Separate facts (from local data) from inference (your recommendation).",
    "- If tools contradict the question, trust tools and say what is missing.",
    "- Never invent SoftDent, QuickBooks, claim, or widget numbers.",
    "",
    "Tool synthesis:",
    "- When tool results are present, weave them into the answer — do not dump raw tool output.",
    "- When grep_program_source ran, cite file paths and line context like a coding agent reviewing the repo.",
    "- When run_hal_validation ran, state pass/fail and summarize failures — do not claim green if validation failed.",
    "- Prefer specific counts, page names, and widget states over generic summaries.",
    "- If a tool failed or returned empty, say so and say what staff should verify.",
    "",
    "Task completion (Cursor-style edit/verify):",
    "- To apply a source patch, staff or you must include a <<<patch block: file, old, new sections.",
    "- After patches, run_hal_validation or run_node_syntax_check should be used before claiming the fix works.",
    "- Never claim code was changed unless apply_program_patch returned ok.",
    "",
    "Confidence language:",
    '- Use "from local imports", "the registry shows", "tool results indicate" when citing data.',
    '- Use "likely" or "probably" only when inferring beyond loaded data.',
    '- Never claim an external action was performed (submit, email, post, fax, upload).',
    "",
    "Tone:",
    "- Clear, direct, collaborative — like a strong coding agent explaining to a colleague.",
    "- Be transparent about what you checked (tools used are visible to staff) without narrating chain-of-thought.",
    "- No sarcasm, no dismissals, no happy-to-help filler, no let-me-know-if closers, no engagement bait.",
    "- Firm on read-only source limits and missing executors; helpful on what HAL can do locally instead.",
  ];

  const TOOL_SYNTHESIS_LINES = [
    "Synthesize tool results into the answer — do not paste tool headers or markdown dumps.",
    "If multiple tools ran, combine them into one coherent picture (snapshot + widgets + source health).",
    "Call out [FAILED] widgets, empty imports, and runtime issues when present.",
  ];

  const SELF_CHECK_RUBRIC = [
    "empty_response",
    "too_few_sentences",
    "instruction_leak",
    "answer_not_first",
    "yes_no_not_direct",
    "identity_monologue",
    "numbered_list_unrequested",
    "chatbot_filler",
    "sarcasm_or_dismissal",
    "engagement_bait",
    "internal_jargon",
    "question_echo",
    "repeats_previous",
    "claimed_external_action",
    "missing_evidence_when_tools",
    "no_next_step",
  ];

  const SARCASM_RE =
    /\b(shocking|try to look surprised|obviously|predictably|frankly|i couldn't have been clearer|by all means|glacial pace|please bore|apparently it didn't land)\b/i;
  const ENGAGEMENT_BAIT_RE =
    /(let me know if|would you like me to|feel free to ask|if you want more detail|i hope this helps|happy to assist|feel free to reach out|say the word)\s*\.?\s*$/i;

  function contract() {
    return CONTRACT_LINES.join("\n");
  }

  function contractSummary() {
    return "Auto-style agent: answer first, cite local evidence, name gaps, one next step, min five sentences, no sarcasm.";
  }

  function toolSynthesisGuide() {
    return TOOL_SYNTHESIS_LINES.join("\n");
  }

  function wrapSystemPrompt(base) {
    return contract() + "\n\n---\n\n" + String(base || "").trim();
  }

  function formatUserTurn(query, threadBlock) {
    const q = String(query || "").trim();
    if (!threadBlock) return q;
    return threadBlock + "\n\nCurrent question:\n" + q;
  }

  function isYesNoQuestion(query) {
    return /^(can you|are you|do you|does |is |was |will you|would you|could you|should i|may i|have you|did you)\b/i.test(
      String(query || "").trim(),
    );
  }

  function yesNoLead(query, route) {
    const intent = route && route.intent ? String(route.intent) : "";
    const blocked =
      intent === "blocked: firewall" ||
      /^blocked:/.test(intent) ||
      intent === "capability:no-executor" ||
      /^capability:(no-executor|blocked)/.test(intent);
    if (blocked) return "No.";
    if (isYesNoQuestion(query)) return "Yes.";
    return "";
  }

  function agentShapeIssues(query, text, route, opts) {
    opts = opts || {};
    const issues = [];
    const body = String(text || "").trim();
    if (!body) return issues;

    if (SARCASM_RE.test(body)) issues.push("sarcasm_or_dismissal");
    if (ENGAGEMENT_BAIT_RE.test(body)) issues.push("engagement_bait");
    if (/\b(local tool check|synthesize tool results|combine th\b|do not paste tool headers)\b/i.test(body)) {
      issues.push("instruction_leak");
    }
    if (/\b(I (submitted|sent|emailed|uploaded|posted|deleted|paid|wired|faxed))\b/i.test(body)) {
      issues.push("claimed_external_action");
    }

    const hasTools = opts.hadToolResults === true;
    const codeDiscuss = opts.codeDiscussion === true;
    if (hasTools && !codeDiscuss && !/\b(from local|registry|import|snapshot|tool|widget|readiness|local data|local check)\b/i.test(body)) {
      issues.push("missing_evidence_when_tools");
    }
    if (
      body.length > 120 &&
      !codeDiscuss &&
      !/\b(refresh|open |run readiness|verify|check import|draft|navigate|next step|staff should|you can ask)\b/i.test(body)
    ) {
      issues.push("no_next_step");
    }
    return issues;
  }

  const EVIDENCE_SUFFIX = "This is based on the local program data gathered for this question.";

  function repairAgentShapeIssues(query, text, issues, route) {
    let out = String(text || "").trim();
    if (issues.includes("sarcasm_or_dismissal")) {
      out = out
        .replace(/\b(yes|no)[—,\s-]*(shocking|obviously|predictably|frankly)[—,\s-]*/gi, "$1. ")
        .replace(SARCASM_RE, "")
        .replace(/\s{2,}/g, " ")
        .trim();
    }
    if (issues.includes("engagement_bait")) {
      out = out.replace(ENGAGEMENT_BAIT_RE, "").trim();
    }
    if (issues.includes("claimed_external_action")) {
      out = out.replace(/\bI (submitted|sent|emailed|uploaded|posted|deleted|paid|wired|faxed)\b/gi, "A human must");
    }
    if (issues.includes("instruction_leak") && typeof HalCore !== "undefined" && HalCore.stripInstructionLeaks) {
      out = HalCore.stripInstructionLeaks(out);
    }
    if (issues.includes("missing_evidence_when_tools") && !/\bbased on the local program data\b/i.test(out)) {
      out = out.replace(/[.!?]\s*$/, "") + " " + EVIDENCE_SUFFIX;
    }
    if (
      issues.includes("no_next_step") &&
      !/\b(next step|you can|staff should|try refreshing|open the)\b/i.test(out)
    ) {
      const nextSuffix = " Next step: refresh imports or name a specific page if you want a narrower check.";
      if (!/\bnext step:\s*refresh imports or name a specific page\b/i.test(out)) {
        out = out.replace(/[.!?]\s*$/, "") + nextSuffix;
      }
    }
    if (issues.includes("yes_no_not_direct") && isYesNoQuestion(query) && !/^(yes|no)\b/i.test(out)) {
      const lead = yesNoLead(query, route || {});
      if (lead) out = lead + " " + out.charAt(0).toLowerCase() + out.slice(1);
    }
    return out.trim();
  }

  global.HalAgentProgramming = {
    VERSION,
    contract,
    contractSummary,
    toolSynthesisGuide,
    wrapSystemPrompt,
    formatUserTurn,
    yesNoLead,
    isYesNoQuestion,
    agentShapeIssues,
    repairAgentShapeIssues,
    SELF_CHECK_RUBRIC,
  };
})(typeof globalThis !== "undefined" ? globalThis : typeof window !== "undefined" ? window : this);

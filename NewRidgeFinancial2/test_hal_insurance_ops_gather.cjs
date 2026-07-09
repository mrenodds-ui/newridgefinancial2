/**
 * Smoke tests for insurance_ops gather recovery helpers in hal-agent.js
 */
const path = require("path");
const HalAgent = require(path.join(__dirname, "site", "hal-agent.js"));

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

assert(typeof HalAgent.wantsInsuranceOpsTools === "function", "exports wantsInsuranceOpsTools");
assert(typeof HalAgent.expandGatherToolsForRound === "function", "exports expandGatherToolsForRound");

assert(HalAgent.wantsInsuranceOpsTools("MetLife eligibility phone"), "phone query is insurance ops");
assert(HalAgent.wantsInsuranceOpsTools("allowed for D2740 on Delta"), "fee query is insurance ops");
assert(!HalAgent.wantsInsuranceOpsTools("What is our revenue this month?"), "revenue is not insurance ops");

const extra = HalAgent.expandGatherToolsForRound(
  "MetLife eligibility phone",
  { useModel: true },
  {},
  1,
  ["read_current_context"]
);
assert(extra.includes("search_payer_reference"), `expected search_payer_reference in ${JSON.stringify(extra)}`);

const feeExtra = HalAgent.expandGatherToolsForRound(
  "allowed for D2740 on Delta Dental",
  { useModel: true },
  { lookup_fee_schedule: { ok: false, summary: "No fee schedule matches.", count: 0 } },
  1,
  ["lookup_fee_schedule"]
);
assert(
  feeExtra.includes("search_hal_memories") || feeExtra.includes("search_payer_reference"),
  `expected recovery tools after empty fee lookup, got ${JSON.stringify(feeExtra)}`
);

const needs = HalAgent.needsMoreGather(
  { pass: false, issues: ["missing_evidence_when_tools"] },
  { search_payer_reference: { ok: false, summary: "No payer reference matches.", count: 0 } },
  { useModelEnhancement: true, originalQuery: "MetLife eligibility phone", tools: ["search_payer_reference"] },
  1
);
assert(needs === true, "needsMoreGather should retry after empty payer hit");

const claimExtra = HalAgent.expandGatherToolsForRound(
  "Why was this claim denied and what is the denial risk?",
  { useModel: true },
  {},
  1,
  ["read_current_context"]
);
assert(claimExtra.includes("read_claims_summary"), `expected read_claims_summary in ${JSON.stringify(claimExtra)}`);
assert(
  claimExtra.includes("predict_claim_denial_risk") || claimExtra.includes("search_payer_reference"),
  `expected denial/payer scrub tools in ${JSON.stringify(claimExtra)}`
);

const preflightExtra = HalAgent.expandGatherToolsForRound(
  "Run claim preflight before submit",
  { useModel: true },
  {},
  1,
  ["read_current_context"]
);
assert(
  preflightExtra.includes("stage_claim_preflight") || preflightExtra.includes("read_claims_summary"),
  `expected preflight/readiness tools in ${JSON.stringify(preflightExtra)}`
);

console.log("test_hal_insurance_ops_gather: ok");

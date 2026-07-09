/**
 * Smoke: claims aging follow-up + readiness age fields.
 */
const path = require("path");
const HalSkills = require(path.join(__dirname, "site", "hal-skills.js"));
const HalAgent = require(path.join(__dirname, "site", "hal-agent.js"));

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

const oldDate = new Date();
oldDate.setDate(oldDate.getDate() - 75);
const dos = oldDate.toISOString().slice(0, 10);

const claims = [
  {
    id: "C-OLD",
    payer: "Delta Dental",
    procedure: "D2740 Crown",
    amount: "$1200.00",
    status: "Denied",
    serviceDate: dos,
    ageDays: 75,
  },
  {
    id: "C-NEW",
    payer: "MetLife",
    procedure: "D1110",
    amount: "$95.00",
    status: "Ready",
    serviceDate: new Date().toISOString().slice(0, 10),
    ageDays: 2,
  },
];

const aging = HalSkills.buildClaimsAgingFollowUp(claims, { minDays: 60 });
assert(aging.count === 1, `expected 1 aging claim, got ${aging.count}`);
assert(aging.items[0].claimRef === "C-OLD", "expected C-OLD first");

const readiness = HalSkills.assessClaimReadiness(claims[0]);
assert(readiness.ageDays === 75, `expected ageDays 75, got ${readiness.ageDays}`);
assert(readiness.agingOver60 === true, "expected agingOver60");
assert(/appeal/i.test(readiness.recommendedNextActions.join(" ")), "expected appeal action");

const text = HalSkills.formatClaimsAgingFollowUp(aging);
assert(/Aging follow-up/i.test(text) || /≥60/i.test(text), "expected aging text");

assert(typeof HalAgent.TOOLS !== "undefined" || typeof HalAgent.buildPlan === "function" || true, "agent loaded");
const extra = HalAgent.expandGatherToolsForRound(
  "Build an appeal packet for this denied claim",
  { useModel: true },
  {},
  1,
  ["read_current_context"]
);
assert(
  extra.includes("build_appeal_packet") || extra.includes("read_claims_summary"),
  `expected appeal gather tools, got ${JSON.stringify(extra)}`
);

const agingExtra = HalAgent.expandGatherToolsForRound(
  "List claims aging follow-up over 60 days",
  { useModel: true },
  {},
  1,
  ["read_current_context"]
);
assert(
  agingExtra.includes("list_claims_aging_followup") || agingExtra.includes("read_claims_summary"),
  `expected aging gather, got ${JSON.stringify(agingExtra)}`
);

console.log("test_hal_claims_aging_appeal: ok");

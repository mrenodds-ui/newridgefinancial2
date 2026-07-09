/**
 * Smoke: morning/office briefings surface packet readiness from HalSkills.
 */
const path = require("path");
const HalSkills = require(path.join(__dirname, "site", "hal-skills.js"));
const HalOfficeManager = require(path.join(__dirname, "site", "hal-office-manager.js"));
const HalProactive = require(path.join(__dirname, "site", "hal-proactive.js"));

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

global.HalSkills = HalSkills;

const old = new Date();
old.setDate(old.getDate() - 80);
const snapshot = {
  claims: {
    total: 3,
    laneTotals: { Denied: 1, "Needs Review": 1, Ready: 1 },
    claims: [
      {
        id: "DS-20260709-1",
        payer: "Insurance",
        procedure: "D2740 Crown",
        amount: "$1200.00",
        status: "Denied",
        serviceDate: old.toISOString().slice(0, 10),
        ageDays: 80,
      },
      {
        id: "C2",
        payer: "Delta Dental",
        procedure: "D1110 Prophy",
        amount: "$95.00",
        status: "Ready",
        narrative: "Prophy completed",
        ageDays: 3,
      },
      {
        id: "C3",
        payer: "Insurance",
        procedure: "D4341 SRP",
        amount: "$400.00",
        status: "Needs Review",
        ageDays: 12,
      },
    ],
  },
};

const brief = HalOfficeManager.claimsReadinessBrief(snapshot);
assert(brief, "claimsReadinessBrief should return data");
assert(brief.genericPayer >= 2, `expected generic payer count, got ${brief.genericPayer}`);
assert(brief.daysheetDerived >= 1, "expected daysheet-derived count");

const officeText = HalOfficeManager.formatDailyOfficeBriefing(
  { summary: "test", posture: "ok", priorities: [], halDid: [] },
  snapshot
);
assert(/Packet readiness/i.test(officeText), "office briefing should mention packet readiness");
assert(/Carrier gap/i.test(officeText), "office briefing should mention carrier gap");
assert(/Aging follow-up/i.test(officeText), "office briefing should mention aging follow-up");

const card = HalProactive.buildMorningBriefingCard(snapshot);
assert(card.claimsSummary && card.claimsSummary.readiness, "morning card should include readiness");
assert(card.claimsSummary.aging && card.claimsSummary.aging.count >= 1, "morning card should include aging");
const morningText = HalProactive.formatMorningBriefingCard(card);
assert(/Packet readiness/i.test(morningText), "morning briefing should mention packet readiness");
assert(/Aging follow-up/i.test(morningText), "morning briefing should mention aging");

console.log("test_hal_briefing_claim_readiness: ok");
